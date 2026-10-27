"""开箱脚本：批量创建家庭成员账号（也可用于自测/演示）。

用法（在 code/backend/src 目录下）：
    python -m scripts.bootstrap_family                     # 用默认四位家人 + 密码 family123
    python -m scripts.bootstrap_family --password 123456   # 自定义初始密码
    python -m scripts.bootstrap_family --list              # 只看现有成员

走数据库直连，不受控制台编码影响，中文昵称不会乱码。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from common.securityCommon import hash_password  # noqa: E402
from db.base import SessionLocal, init_db  # noqa: E402
from db.models import User  # noqa: E402
from tools.seedPresets import install_presets  # noqa: E402

DEFAULT_MEMBERS = [
    ("father", "爸爸", "#C9A063"),
    ("mother", "妈妈", "#2E7D5B"),
    ("sister", "姐姐", "#C0392B"),
    ("brother", "弟弟", "#4A7EBB"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="批量创建家庭成员账号")
    parser.add_argument("--password", default="family123", help="初始密码，默认 family123")
    parser.add_argument("--list", action="store_true", help="只列出当前成员")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as session:
        install_presets(session)
        if args.list:
            for user in session.scalars(select(User).order_by(User.id)).all():
                print(f"{user.id:>3}  {user.username:<10} {user.display_name:<6} {user.role}")
            return

        created = 0
        for username, display, color in DEFAULT_MEMBERS:
            exists = session.scalar(select(User).where(User.username == username))
            if exists is not None:
                exists.display_name = display
                exists.color = color
                continue
            session.add(
                User(
                    username=username,
                    display_name=display,
                    password_hash=hash_password(args.password),
                    role="member",
                    color=color,
                )
            )
            created += 1
        session.commit()
        print(f"新建 {created} 位成员，初始密码：{args.password}")


if __name__ == "__main__":
    main()
