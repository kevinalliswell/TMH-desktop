"""运行时配置文件不得处于「既未跟踪也未忽略」的状态。

仓库已转为 public，因此这个中间状态是有后果的：一次 `git add configs/` 就会把
现场机器的运行时数据发布出去，其中 `configs/password_config.json` 存的是管理员
口令的 PBKDF2 哈希与盐值。它此前既不在版本库里、也不被 .gitignore 覆盖，纯靠
没人误提交才没出事。

断言的是集合性质而不是某几行文本：凡是代码会通过 PathManager 读写的配置路径，
要么被跟踪（属于仓库内容），要么被忽略（属于现场数据），不允许悬在中间。将来新增
一个运行时配置文件时，这条会直接要求作者表态，而不是又留一个缺口。
"""
import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 代码里取配置路径的唯一入口（见 CLAUDE.md：路径一律走 PathManager）。
_CONFIG_PATH_CALL = re.compile(r"get_config_path\(\s*['\"]([^'\"]+)['\"]")


def _config_names() -> set[str]:
    """所有经 PathManager 访问的 configs/ 下的名字。"""
    names: set[str] = set()
    for source in (PROJECT_ROOT / "src").rglob("*.py"):
        names |= set(_CONFIG_PATH_CALL.findall(source.read_text(encoding="utf-8")))
    return names


def _is_tracked(relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def _is_ignored(relative_path: str) -> bool:
    """check-ignore 的退出码：0 = 被忽略，1 = 未被忽略。

    目录型规则（`configs/gas_programs/`）不会匹配不带尾斜杠、且磁盘上尚不存在的
    路径，所以目录还要用「目录内的一个文件」再探一次——那才是 git 真会被要求
    暂存的路径形态。
    """
    for candidate in (relative_path, f"{relative_path}/.probe"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", candidate],
            cwd=PROJECT_ROOT,
            capture_output=True,
        )
        if result.returncode == 0:
            return True
    return False


def test_every_runtime_config_path_is_either_tracked_or_ignored():
    names = _config_names()
    assert names, "未从 src/ 解析出任何 get_config_path 调用，正则或路径约定已变"

    limbo = [
        name
        for name in sorted(names)
        if not _is_tracked(f"configs/{name}") and not _is_ignored(f"configs/{name}")
    ]
    assert not limbo, (
        "以下配置路径既未被跟踪也未被忽略，一次 git add configs/ 就会把它们提交进"
        f"公开仓库：{limbo}。请决定它属于仓库内容（跟踪）还是现场数据（加入 .gitignore）。"
    )


def test_the_admin_password_store_is_ignored_and_untracked():
    """单列一条：这个文件存的是凭据摘要，不是普通运行时数据。

    PasswordManager 默认写到 configs/password_config.json（password_manager.py 的
    __init__）。若该文件名被改，上面那条会以新名字继续抓住缺口；这条则保证改名时
    连带这条断言一起被注意到。
    """
    store = "configs/password_config.json"
    assert not _is_tracked(store), f"{store} 存着口令哈希与盐值，绝不能进版本库"
    assert _is_ignored(store), f"{store} 未被 .gitignore 覆盖，误提交无人拦截"
