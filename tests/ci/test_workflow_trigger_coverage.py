"""CI 触发范围的回归护栏。

`.github/workflows/ci.yml` 曾把 `pull_request` 的目标分支限定为 `[main, develop]`。
后果不是「CI 失败」而是「CI 根本不运行」：凡以集成分支为目标的 PR，check runs 数
恒为 0，PR 描述里的绿灯全部来自作者本地执行。这类缺陷不产生任何报错、不留下任何
红叉，只能靠断言钉住——否则下一次收窄同样会静默生效。
"""
from pathlib import Path

# PyYAML 与 pytest 同属 requirements-dev.txt。此处刻意用硬导入而非
# importorskip：一个「装不上就自动跳过」的护栏，和它要防的静默失效是同一种病。
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _load_workflow(filename: str) -> dict:
    path = WORKFLOWS / filename
    assert path.is_file(), f"缺少工作流文件：{path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    """取出 `on:` 块。

    YAML 1.1 把裸 `on` 解析成布尔 `True`（PyYAML 遵循 1.1），而 GitHub 读的是
    字符串键。两种键都要认，否则护栏会因为解析细节而假绿。
    """
    for key in ("on", True):
        if key in workflow:
            return workflow[key]
    raise AssertionError(f"工作流没有 on: 触发块，键为 {sorted(map(str, workflow))}")


def _branch_filter(trigger) -> list | None:
    """返回该触发器的 branches 过滤器；None 表示不限定分支。"""
    if not isinstance(trigger, dict):
        return None  # `pull_request:` 下没有任何子键，即不限定
    return trigger.get("branches")


def test_pull_request_runs_regardless_of_base_branch():
    """任何 PR 都必须跑 CI，不论目标分支是什么。

    这是 PR #79–#116 全部零 check run 的直接原因：它们的目标是集成分支
    `feature/issues-review-integration`，不在当时的 `[main, develop]` 清单里。
    """
    triggers = _triggers(_load_workflow("ci.yml"))
    assert "pull_request" in triggers, "pull_request 必须能触发 CI"

    branches = _branch_filter(triggers["pull_request"])
    if branches is not None:
        assert "**" in branches, (
            f"pull_request 的 branches 把目标分支收窄成了有限清单：{branches}。"
            "清单外分支的 PR 会静默地一次 CI 都不跑——不是失败，是不触发。"
            '请用 "**"，或整个删掉 branches 过滤器。'
        )


def test_push_covers_the_long_lived_integration_branches():
    """集成分支的推送必须跑 CI。

    跨 PR 的语义合并缺陷——每个 PR 单看都正确，合到一起才出错——只有在合并后的
    集成分支上才暴露得出来，话题分支上的 PR 检查看不见它。
    """
    triggers = _triggers(_load_workflow("ci.yml"))
    assert "push" in triggers, "push 必须能触发 CI"

    branches = _branch_filter(triggers["push"])
    if branches is None:
        return  # 不限定分支，天然覆盖

    for required in ("main", "develop"):
        assert required in branches or "**" in branches, (
            f"集成分支 {required} 不在 push 触发清单 {branches} 内，"
            "合并后的回归将无人检查"
        )


def test_tag_pushes_are_handled_by_release_only():
    """`v*` 标签只应触发 Release，不应额外触发一遍 CI。

    两个工作流的标签过滤必须保持互补：任何一侧改动而另一侧没跟上，都会导致标签
    推送要么跑两遍、要么两边都不跑。
    """
    ci_push = _triggers(_load_workflow("ci.yml"))["push"]
    release_push = _triggers(_load_workflow("release.yml"))["push"]

    assert "v*" in (ci_push.get("tags-ignore") or []), "CI 应忽略 v* 标签推送"
    assert "v*" in (release_push.get("tags") or []), "Release 应响应 v* 标签推送"
