# MinerU Desk 本地接口

依据用户提供的 Desk 0.3.1 接入说明和随包 agent.mjs。安装更新后以实际接口为准。以下 $deskRoot 由主 Skill 定位流程得出。

## 诊断

```powershell
$deskCli = Join-Path $deskRoot 'Codex.ps1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deskCli verify
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deskCli doctor
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deskCli request GET state
```

依次检查退出码；失败时不要继续提交。Bypass 只作用于该进程，不改全局策略或绕过组织限制。不要打印连接文件；状态仅展示所需字段，避免输出无关任务资料。

队列空闲、未暂停、无模型下载任务且离线设置为真时：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deskCli self-test
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deskCli self-test --pdf
```

退出码 0 为该命令成功；1 为调用错误；2 为测试失败或缺少条件。还要读 status/checks。PDF 的 needs-models 表示未执行推理；doctor 的 path-present-unverified 仅表示找到路径。

自检创建合成样本任务，核查文字、图片、源文件哈希和缓存复用；报告在 identity.dataRoot。模型导入后仍须实测。

## 提交

变量设置为实际文件和项目目录。用序列化生成 JSON，不把用户文本拼接为命令：

```powershell
$requestBody = @{
    files = @($sourceFile)
    outputRoot = $outputDirectory
    options = @{
        provider = 'local'
        backend = 'pipeline'
        method = 'auto'
        pages = '1-3'
        formula = $true
        table = $true
        timeout = 600
    }
}
$requestJson = $requestBody | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($requestFile, $requestJson, [Text.UTF8Encoding]::new($false))
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deskCli submit $requestFile
```

pages 仅用于 PDF 小样本，不足三页时调整；全文和 Office 任务省略。批量扩展 files 数组，分别跟踪响应数组中的任务 ID。输入必须存在，输出可写且在安装目录之外。

提交成功仅代表入队。保存 ID 后查询：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deskCli request GET "tasks/$taskId"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $deskCli request GET "tasks/$taskId/content"
```

0.3.1 任务详情提供 status、markdown、outputDir，内容响应有 original。存在用户编辑版本时保留它，不能用原始解析覆盖。批量报告部分成功/失败。检查图片相对路径，不只复制一个 MD。

## 按需排障

只读接口：identity、models、hardware、storage、services、state。通用语法为 request GET|POST 路由 [JSON文件]，路由不带 /api/。

- 内存不足或解析失败：读取该任务错误，减少页数做针对性复现，不反复提交相同请求。
- 缺模型：报告路径与下载/导入选择，不把目录存在等同模型完整。
- CPU 包按 CPU 运行；显卡名称不能证明 CUDA 可用。不升级驱动或 pip 修改随包环境。
- 身份不匹配：报告目录/版本冲突，不删除连接文件、强停其他版本或批量杀进程。
- 查询超时：保留任务 ID，后续继续查询，不重新提交。
- 缺 OCR/页码：报告未识别范围和无法核验的内容，不补写论文事实。

通常无需直接 HTTP。Codex.ps1 已处理隐藏启动、Bearer 认证和 identity 核验。确需排障时读取安装说明中的连接协议，不输出 token。

本机实测遇到过首次版本探测超过服务的 30 秒限制：若 verify 通过且 doctor 仅报本地版本探测超时，可在无相关活动任务时，用随包 runtime/python.exe 执行 runtime/mineru-cli.py --version 做一次有界复核（最多等待 120 秒），再重试 doctor 一次。成功后继续；仍失败则报告阻塞，不重装或修改程序的超时/依赖。该复核不转换文件，不下载模型，不代表 PDF 推理成功。
