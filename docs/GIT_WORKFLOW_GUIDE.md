# TMH项目 Git版本管理流程指南

## 项目概述
TMH (Temperature, Mass Flow, Humidity) 项目是一个综合性的工业控制和数据采集系统，包含桌面应用程序和Web系统两个主要组件。

## 仓库结构
```
TMH/
├── .gitignore                 # Git忽略文件配置
├── GIT_WORKFLOW_GUIDE.md     # 本文档
├── TMH1.0.250818/           # 桌面应用程序
│   ├── src/                 # 源代码目录
│   │   ├── analysis/        # 分析模块 (GB13240, GB13241, GB13242)
│   │   ├── device_clients/  # 设备客户端
│   │   ├── ui/             # 用户界面
│   │   └── utils/          # 工具类
│   ├── configs/            # 配置文件
│   └── requirements.txt    # Python依赖
└── TMH_Web_System/         # Web系统
    ├── backend/            # 后端API
    ├── frontend/           # 前端模板和静态文件
    ├── app.py             # Flask应用入口
    └── requirements.txt    # Web系统依赖
```

## Git配置

### 1. 初始设置
```bash
# 设置用户信息
git config --global user.name "kevinalliswell"
git config --global user.email "kevin.alliswell@gmail.com"

# 设置行尾符处理（Windows环境推荐）
git config --global core.autocrlf true
```

### 2. 克隆仓库
```bash
git clone https://github.com/kevinalliswell/TMH.git
cd TMH
```

## 日常开发流程

### 1. 开始新功能开发
```bash
# 确保在最新的main分支
git checkout main
git pull origin main

# 创建新的功能分支
git checkout -b feature/新功能名称
# 例如: git checkout -b feature/web-dashboard
```

### 2. 进行开发工作
```bash
# 查看修改状态
git status

# 查看具体修改内容
git diff

# 添加修改的文件
git add 文件名
# 或添加所有修改
git add .
```

### 3. 提交更改
```bash
# 提交更改（使用有意义的提交信息）
git commit -m "feat: 添加Web仪表板功能"

# 提交信息规范建议：
# feat: 新功能
# fix: 修复bug
# docs: 文档更改
# style: 代码格式化
# refactor: 代码重构
# test: 添加测试
# chore: 构建过程或辅助工具的变动
```

### 4. 推送更改
```bash
# 首次推送新分支
git push -u origin feature/新功能名称

# 后续推送
git push
```

### 5. 创建Pull Request
1. 在GitHub上访问仓库页面
2. 点击"Compare & pull request"按钮
3. 填写PR标题和描述
4. 指定审核人员
5. 创建Pull Request

### 6. 合并到主分支
```bash
# PR审核通过后，切换到main分支
git checkout main
git pull origin main

# 如果使用命令行合并（推荐在GitHub上操作）
git merge feature/新功能名称
git push origin main

# 删除已合并的分支
git branch -d feature/新功能名称
git push origin --delete feature/新功能名称
```

## 分支管理策略

### 主分支
- **main**: 生产环境代码，始终保持稳定可部署状态

### 开发分支
- **feature/功能名**: 新功能开发分支
- **bugfix/问题描述**: Bug修复分支
- **hotfix/紧急修复**: 生产环境紧急修复分支

### 分支命名规范
```
feature/web-authentication    # Web认证功能
feature/device-communication  # 设备通信功能
bugfix/login-error           # 登录错误修复
hotfix/security-patch        # 安全补丁
```

## 常用Git命令

### 查看状态和历史
```bash
git status                    # 查看工作区状态
git log --oneline            # 查看提交历史
git log --graph --oneline    # 图形化提交历史
git show 提交ID              # 查看特定提交详情
```

### 撤销操作
```bash
git checkout -- 文件名       # 撤销工作区修改
git reset HEAD 文件名        # 取消暂存
git reset --soft HEAD~1      # 撤销最后一次提交（保留修改）
git reset --hard HEAD~1      # 撤销最后一次提交（删除修改）
```

### 分支操作
```bash
git branch                   # 查看本地分支
git branch -a               # 查看所有分支
git checkout 分支名          # 切换分支
git checkout -b 新分支名     # 创建并切换到新分支
git branch -d 分支名         # 删除本地分支
```

### 远程仓库操作
```bash
git remote -v               # 查看远程仓库
git fetch origin            # 获取远程更新
git pull origin main        # 拉取并合并远程主分支
git push origin 分支名       # 推送到远程分支
```

## 代码提交规范

### 提交信息格式
```
<类型>(<范围>): <描述>

<详细说明>

<脚注>
```

### 示例
```
feat(web): 添加用户认证功能

- 实现用户登录和注册接口
- 添加JWT token验证
- 完善权限控制中间件

Closes #123
```

### 类型说明
- **feat**: 新功能
- **fix**: 修复
- **docs**: 文档
- **style**: 格式
- **refactor**: 重构
- **perf**: 性能优化
- **test**: 测试
- **chore**: 构建过程或辅助工具的变动

## 版本标签管理

### 创建版本标签
```bash
# 创建轻量标签
git tag v1.0.0

# 创建附注标签（推荐）
git tag -a v1.0.0 -m "发布版本 1.0.0"

# 推送标签到远程
git push origin v1.0.0
# 或推送所有标签
git push origin --tags
```

### 版本号规范 (语义化版本)
```
主版本号.次版本号.修订号 (MAJOR.MINOR.PATCH)

1.0.0 - 初始发布版本
1.1.0 - 添加新功能，向后兼容
1.0.1 - 修复bug，向后兼容
2.0.0 - 重大更改，可能不向后兼容
```

## 协作开发注意事项

### 1. 代码审查
- 所有代码必须通过Pull Request进行审查
- 至少需要一名团队成员审核
- 确保代码符合项目规范

### 2. 冲突解决
```bash
# 当出现合并冲突时
git status                   # 查看冲突文件
# 手动编辑冲突文件，解决冲突
git add 冲突文件名
git commit -m "resolve: 解决合并冲突"
```

### 3. 保持同步
```bash
# 定期同步主分支
git checkout main
git pull origin main
git checkout feature/your-branch
git rebase main  # 或使用 git merge main
```

## 备份和恢复

### 1. 创建备份
```bash
# 备份整个仓库
git clone --mirror https://github.com/kevinalliswell/TMH.git TMH-backup.git

# 备份特定分支
git archive --format=zip --output=backup.zip HEAD
```

### 2. 数据恢复
```bash
# 恢复已删除的提交
git reflog                   # 查看引用日志
git checkout 提交ID           # 恢复到特定提交

# 恢复已删除的分支
git checkout -b 分支名 提交ID
```

## 性能优化

### 1. 仓库清理
```bash
# 清理无用的引用
git gc --prune=now

# 清理远程追踪分支
git remote prune origin
```

### 2. 大文件处理
- 使用 `.gitignore` 忽略大文件
- 考虑使用 Git LFS 管理大型二进制文件
- 定期清理不需要的文件

## 安全考虑

### 1. 敏感信息保护
- 配置文件中的密码和密钥不要提交
- 使用环境变量管理敏感配置
- 定期检查提交历史中的敏感信息

### 2. 访问控制
- 设置适当的仓库权限
- 使用SSH密钥进行安全认证
- 启用两因素认证

## 故障排除

### 常见问题和解决方案

1. **推送被拒绝**
   ```bash
   git pull origin main --rebase
   git push origin main
   ```

2. **提交信息错误**
   ```bash
   git commit --amend -m "正确的提交信息"
   ```

3. **意外删除文件**
   ```bash
   git checkout HEAD -- 文件名
   ```

4. **合并冲突**
   - 手动编辑冲突文件
   - 删除冲突标记 (`<<<<<<<`, `=======`, `>>>>>>>`)
   - 保存文件并提交

## 联系信息

- **仓库地址**: https://github.com/kevinalliswell/TMH
- **维护者**: kevinalliswell
- **邮箱**: kevin.alliswell@gmail.com

---

*本文档会根据项目发展持续更新，建议定期查看最新版本。*
