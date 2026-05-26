"""Idempotent seed script. Run with: python -m app.utils.seed"""
import asyncio
import uuid
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings

BUSINESS_TYPES = [
    {"code": "trade", "name": "Торговля", "name_cn": "贸易"},
    {"code": "logistics", "name": "Логистика", "name_cn": "物流"},
    {"code": "services", "name": "Услуги", "name_cn": "服务"},
]

EXPENSE_CATEGORIES = [
    {"name": "Транспорт", "name_cn": "运输"},
    {"name": "Представительские", "name_cn": "招待"},
    {"name": "Аренда офиса", "name_cn": "办公室租金"},
    {"name": "Канцелярия", "name_cn": "办公用品"},
    {"name": "Связь и интернет", "name_cn": "通讯网络"},
    {"name": "Командировки", "name_cn": "差旅"},
    {"name": "Зарплата", "name_cn": "工资"},
    {"name": "Брокерские услуги", "name_cn": "报关费"},
    {"name": "Банковские комиссии", "name_cn": "银行手续费"},
    {"name": "Прочее", "name_cn": "其他"},
]


async def run_seed() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    from app.models.company import Company
    from app.models.user import User, UserRole, UserLang
    from app.models.business_type import BusinessType
    from app.models.expense_category import ExpenseCategory

    async with Session() as session:
        # Company
        result = await session.execute(select(Company).where(Company.name == "Моя компания"))
        if not result.scalar_one_or_none():
            session.add(Company(id=uuid.uuid4(), name="Моя компания", name_cn="我的公司", is_active=True))
            print("  + Company created")
        else:
            print("  = Company already exists")

        # Business types
        for bt in BUSINESS_TYPES:
            result = await session.execute(select(BusinessType).where(BusinessType.code == bt["code"]))
            if not result.scalar_one_or_none():
                session.add(BusinessType(id=uuid.uuid4(), **bt))
                print(f"  + BusinessType '{bt['code']}' created")
            else:
                print(f"  = BusinessType '{bt['code']}' already exists")

        # Expense categories
        for cat in EXPENSE_CATEGORIES:
            result = await session.execute(select(ExpenseCategory).where(ExpenseCategory.name == cat["name"]))
            if not result.scalar_one_or_none():
                session.add(ExpenseCategory(id=uuid.uuid4(), **cat, is_active=True))
                print(f"  + ExpenseCategory '{cat['name']}' created")
            else:
                print(f"  = ExpenseCategory '{cat['name']}' already exists")

        # Admin user
        result = await session.execute(select(User).where(User.login == "admin"))
        if not result.scalar_one_or_none():
            pw_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            session.add(User(
                id=uuid.uuid4(),
                login="admin",
                password_hash=pw_hash,
                full_name="Администратор",
                role=UserRole.admin,
                lang=UserLang.ru,
                is_active=True,
            ))
            print("  + Admin user created")
        else:
            print("  = Admin user already exists")

        await session.commit()

    await engine.dispose()
    print("\nSeed completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_seed())
