# edit-snapshot

`edit-snapshot` 是一个面向文件改动任务的本地 Git 保护 skill。

它的目标很简单。在真正修改工作区文件之前，先留下一个可恢复的 Git 快照。修改完成后，再把最近提交历史和可回退方式明确展示给用户。

这一版维持 1.4 系列的整仓库保护策略，不要求预先声明文件路径。它更适合做一个默认安全动作，只要任务会写文件，就先做一次快照。

## 适用场景

建议在这些任务开始前使用。

- 创建文件或脚本
- 编辑现有文件
- 覆盖、删除、重命名文件
- 批量重构
- 修改配置
- 生成代码、文档或其他输出文件
- 运行会写入工作区的 shell 命令
- `apply_patch` 或其他补丁式修改

不适合这些场景。

- 只读查看
- 搜索、grep、diff-only 分析
- 纯解释类任务

## 设计原则

这个 skill 是安全垫，不是完整的 Git 工作流管理器。

它的核心原则是。

- 先保护，再动文件
- 宁可多触发，也不要漏触发
- 小任务也要保护，不以“改动很简单”为理由跳过
- 修改完成后要明确告诉用户快照和回退信息

## 工作流程

### 1. 修改前

在第一次写文件前执行。

```bash
{baseDir}/scripts/helper.sh pre "<short reason>"
```

这一步会。

- 发现并复用当前仓库，或在当前目录初始化仓库
- 补齐 repo-local Git identity
- 在需要时创建 PRE 快照
- 保存本次最近一次保护状态

### 2. 修改中

正常执行文件编辑、补丁应用、代码生成或其他写操作。

### 3. 修改后

执行。

```bash
{baseDir}/scripts/helper.sh post "<short reason>"
{baseDir}/scripts/helper.sh recent 5
{baseDir}/scripts/helper.sh rollback-help
```

这一步会。

- 在有新变化时创建 POST 快照
- 输出最近提交记录
- 输出常见回退方式

## 给用户的回报内容

完成后，建议明确告诉用户这些信息。

- 仓库根目录
- PRE 快照
- POST 快照是否存在
- 最近几次提交
- 支持回退
- 优先推荐的回退命令

## 行为边界

### 它会做什么

- 只做本地 Git 快照
- 在当前目录所属仓库中工作
- 必要时自动 `git init`
- 必要时补本地 `user.name` 和 `user.email`
- 在失败时显式报错

### 它不会做什么

- 不会自动 `git push`
- 不会自动 `git pull`、`fetch`、`merge`、`rebase`
- 不会自动回退
- 不会替用户做远端协作决策
- 不会在没有 PRE 的情况下静默执行 POST

## 已知边界

这一版是整仓库保护。

这意味着如果仓库在任务开始前本来就是脏的，PRE 快照可能会把已有未提交改动一起保存进去。非 `.gitignore` 的新增文件、生成物、二进制文件，以及误放到工作区的敏感文件，也可能被一起纳入快照。

## 推荐回退命令

```bash
git revert <post_sha>
git reset --hard <pre_sha>
git reflog -n 10
```

其中。

- `git revert <post_sha>` 适合保留历史地撤销本次结果提交
- `git reset --hard <pre_sha>` 适合直接回到修改前状态
- `git reflog -n 10` 用来查看更多可恢复位置
