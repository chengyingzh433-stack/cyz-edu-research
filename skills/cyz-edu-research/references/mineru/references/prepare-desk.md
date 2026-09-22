# 缺少 Desk 时的准备

这是用户自己的 [MinerU Desk](https://github.com/chengyingzh433-stack/mineru-desk)，不是官方新版 MinerU CLI，也不是另一个同名 Skill。

先完成主 Skill 的定位。找到完整安装就使用它；不要因全局 Skill 目录缺少 mineru 而下载程序。本工作流已带上接入 Skill。

## 获取安装包

现有缓存适配器验证的是 Desk 0.3.1 / MinerU 3.4.5。没有安装时使用下面固定版本，不把 latest 当作兼容承诺。安装包约 584 MiB，不含额外下载的模型。

- 文件：MinerU-Desk-Setup-0.3.1-x64.exe
- 下载：[v0.3.1 安装包](https://github.com/chengyingzh433-stack/mineru-desk/releases/download/v0.3.1/MinerU-Desk-Setup-0.3.1-x64.exe)
- 字节数：612375163
- SHA-256：9bc9324e0b1341b51fe7df04eeba21f4edbea6d0ac4395c72207fe2359487083

缺少程序时，先说明下载体积和来源，再在当前项目的下载目录获取。用户已要求缺少就下载时直接执行，不重复询问；明确禁止联网、组织限制或权限不足时记录阻塞，不绕过限制。只访问上述作者仓库，不使用要求账号密码的第三方镜像。

下面的目录变量由调用方设置为项目内的绝对路径。已存在文件先校验，不覆盖其他文件；下载失败保留部分文件供诊断，不执行它。

```powershell
$installerName = 'MinerU-Desk-Setup-0.3.1-x64.exe'
$expectedHash = '9bc9324e0b1341b51fe7df04eeba21f4edbea6d0ac4395c72207fe2359487083'
$expectedBytes = 612375163
$installerUrl = 'https://github.com/chengyingzh433-stack/mineru-desk/releases/download/v0.3.1/MinerU-Desk-Setup-0.3.1-x64.exe'
New-Item -ItemType Directory -Path $downloadDirectory -Force | Out-Null
$installerPath = Join-Path $downloadDirectory $installerName
if (-not (Test-Path -LiteralPath $installerPath)) {
    $partialPath = Join-Path $downloadDirectory ("$installerName." + [guid]::NewGuid().ToString('N') + '.partial')
    curl.exe --fail --location --connect-timeout 30 --max-time 1800 --output $partialPath $installerUrl
    if ($LASTEXITCODE -ne 0) { throw 'Desk 下载失败；不能视为已安装。记录网络错误后决定下一步。' }
    if ((Get-Item -LiteralPath $partialPath).Length -ne $expectedBytes -or
        (Get-FileHash -LiteralPath $partialPath -Algorithm SHA256).Hash -ne $expectedHash) {
        throw '安装包大小或 SHA-256 不符；禁止运行，不覆盖已有安装。'
    }
    Move-Item -LiteralPath $partialPath -Destination $installerPath
}
if ((Get-Item -LiteralPath $installerPath).Length -ne $expectedBytes -or
    (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash -ne $expectedHash) {
    throw '已有安装包校验失败；禁止运行。'
}
```

网络调用使用可返回进度的终端会话，不等待整段下载结束才沟通。最多一次原地址重试；不要无限下载。

## 安装和复核

普通“读论文”请求不能擅自安装大程序或下载模型；本任务已有缺失下载授权，不等于可以改驱动或绕过系统权限。用户已授权安装时，使用此安装包的正常安装流程和用户选择的位置。未确认静默参数时不要猜参数；需要选择目录或系统确认就说明这一小步，等待完成，不能趁等待切备用转换。

安装完成后重新读取 HKCU:\Software\MinerUDesk 的 InstallDir，核对 Codex.ps1、包清单、随包 Python 和桌面 EXE；按主 Skill 做 verify、doctor、state，检查模型后再做小样本解析。缺模型应按该 Desk 的实际模型管理接口处理，有下载/导入授权才执行。不要 pip 安装官方 MinerU 替代 Desk。

## 真正无法继续

只有准备或有界修复已经失败（例如两次下载均失败、安装被系统阻止、无可用模型且无法下载/导入、同一输入小样本仍解析失败），或用户明确选择备用转换，才进入工作流的原生转换路径。

说明实际尝试和错误，不把未尝试说成失败。将原因传给 --fallback-reason，并报告 OCR、表格、公式和双栏顺序的缺失；原文件不修改。任务排队、暂停、查询超时不是解析失败，保留任务 ID 等待或排障，不能重复提交后直接降级。
