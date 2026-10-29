# 从本地文件推送到 GitHub：Windows 入门

本次使用的账号：`qizhou-hust`；公开仓库：`qizhou-hust/yuanqi-public`。

本次本地工作副本：

```text
D:\my_Works\Gears\github-publish\yuanqi-public
```

资料在仓库中的目录：

```text
ai-shared/M33-standards-and-reports-2026-10-28
```

## 先理解四步

1. **clone**：把 GitHub 仓库下载到本地，并建立连接。通常只做一次。
2. **add**：选择本次准备提交的文件。
3. **commit**：在本地创建一个有说明的版本；这时还没有上传。
4. **push**：把本地版本上传到 GitHub。

`git status` 用于查看哪些文件变了。`origin` 是 GitHub 仓库的远程别名，`main` 是这里使用的主分支。

## 以后更新这个资料包

先在资源管理器里把新文件复制到上面的资料目录。打开 PowerShell，逐条运行下面的命令。不要复制行首提示符，不需要输入密码或令牌到命令中。

```powershell
Set-Location 'D:\my_Works\Gears\github-publish\yuanqi-public'
git status
git pull --ff-only origin main
git add -- 'ai-shared/M33-standards-and-reports-2026-10-28'
git diff --cached --stat
git commit -m 'docs: update M33 evidence'
git push origin main
```

提交前检查 `git diff --cached --stat` 列出的文件是否正是你要公开的材料。最后打开 GitHub 仓库页面，刷新后查看最新提交。
如果 `pull` 提示本地修改会被覆盖，先停下，不要运行强制覆盖命令；可以先提交自己的修改，再让协作者帮你处理冲突。
如果提示 `nothing to commit`，表示文件没有变化，不需要重复提交。

这个工作副本最初采用稀疏检出，避免重新下载原仓库的大 ZIP；已显示本次资料目录。需要在资源管理器里看到仓库全部旧文件时，可运行：

```powershell
git sparse-checkout disable
```

## 换一台电脑或第一次使用

安装 Git for Windows 和 GitHub CLI。重新打开 PowerShell，然后：

```powershell
git --version
gh --version
gh auth login
```

在登录向导中选择 GitHub.com、HTTPS、通过浏览器登录；按提示在浏览器里完成授权。GitHub 网站密码不能作为 Git HTTPS 密码。

设置自己的提交署名（替换为你的真实姓名和 GitHub 的提交邮箱；GitHub Settings → Emails 可查看 noreply 邮箱）：

```powershell
git config --global user.name '你的署名'
git config --global user.email '你的GitHub提交邮箱'
```

选择一个存放代码的目录，下载仓库：

```powershell
Set-Location 'D:\my_Works'
gh repo clone qizhou-hust/yuanqi-public
Set-Location '.\yuanqi-public'
```

把要上传的文件复制进这个仓库，再按上面的 add → commit → push 操作。不要把整个 `D:\my_Works\Gears` 直接初始化并全部上传，以免带入不相关的大文件或私人资料。

## ZIP 和大文件应该怎么传

GitHub 普通 Git 提交限制单个文件不能超过 **100 MiB**；网页上传单个文件上限通常为 **25 MiB**。大 ZIP 使用 **Releases 附件**，每个附件可达 **2 GiB**。本次完整包就是 Release 附件，同时把展开后的文件放进仓库，方便 AI 逐个读取。

在已登录的 PowerShell 中，创建新版本并上传 ZIP 的示例（替换文件路径、版本号与标题）：

```powershell
gh release create m33-v2 'D:\my_Works\Gears\你的新包.zip' --repo qizhou-hust/yuanqi-public --target main --title 'M33 资料第二版' --notes '说明本版更新了什么'
```

建议每次使用新版本号和新文件名，保留旧版本，便于外部 AI 引用和复核。不建议把几百 MB 的 ZIP 反复提交到 Git 历史里。Release ZIP 是一个冻结快照；以后 push 更新仓库不会自动更新旧 ZIP。

## 如何让外部 AI 读取

优先提供 `AI_START_HERE.md` 的 **Raw 链接**，而不是只给仓库首页或压缩包。

- GitHub 文件页：适合人浏览，形式为 `github.com/账号/仓库/blob/main/路径`。
- Raw 链接：直接返回文件内容，形式为 `raw.githubusercontent.com/账号/仓库/main/路径`。
- 固定版本：把 Raw URL 中的 `main` 换成发布标签或完整提交 SHA，可避免后续修改影响复现。
- Release 下载链接：适合有文件下载和解压能力的 AI；浏览器型 AI 不一定能处理大 ZIP。

AI 是否能联网、读取 PDF 或解压文件，取决于外部工具本身。让它先读入口文件，再读 CSV/JSON/TXT；标准 OCR 仅供检索，公式以 PDF 原图为准。

## 常见问题

| 提示 | 怎么处理 |
|---|---|
| not a git repository | 先 `Set-Location` 到克隆出来的仓库目录 |
| Authentication failed | 运行 `gh auth login` 重新登录，不要把令牌写进脚本或聊天 |
| rejected / fetch first | 先 `git pull --ff-only`；若提示分叉，停止并处理冲突，不要强推 |
| file exceeds 100 MB | 改用 Release 附件；若已提交到本地历史，需要先修正该提交 |
| nothing to commit | 没有新的文件变化，无须重复提交 |

公开仓库任何人都能读取；发布前检查文件中的密码、令牌、客户信息和第三方资料的公开传播范围。
