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

WAREHOUSES = [
    {"name": "Гуанчжоу", "name_cn": "广州仓", "city": "Guangzhou"},
    {"name": "Иу", "name_cn": "义乌仓", "city": "Yiwu"},
    {"name": "Шэньчжэнь", "name_cn": "深圳仓", "city": "Shenzhen"},
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

USERS = [
    {
        "login": "admin",
        "password": "admin123",
        "full_name": "Администратор",
        "full_name_cn": "管理员",
        "roles": ["admin"],
        "lang": "ru",
    },
    {
        "login": "manager1",
        "password": "test123",
        "full_name": "Менеджер Иван",
        "full_name_cn": "经理伊万",
        "roles": ["manager"],
        "lang": "ru",
    },
    {
        "login": "purchaser1",
        "password": "test123",
        "full_name": "Закупщик Ли",
        "full_name_cn": "采购李",
        "roles": ["purchaser"],
        "lang": "ru",
    },
    {
        "login": "accountant1",
        "password": "test123",
        "full_name": "Бухгалтер Мария",
        "full_name_cn": "会计玛丽亚",
        "roles": ["accountant"],
        "lang": "ru",
    },
]


async def run_seed() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    from app.models.company import Company
    from app.models.user import User, UserLang
    from app.models.user_role import UserRoleEntry
    from app.models.business_type import BusinessType
    from app.models.expense_category import ExpenseCategory
    from app.models.warehouse import Warehouse

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

        # Warehouses
        for wh in WAREHOUSES:
            result = await session.execute(select(Warehouse).where(Warehouse.name == wh["name"]))
            if not result.scalar_one_or_none():
                session.add(Warehouse(id=uuid.uuid4(), **wh, is_active=True))
                print(f"  + Warehouse '{wh['name']}' created")
            else:
                print(f"  = Warehouse '{wh['name']}' already exists")

        await session.commit()

        # Expense categories
        for cat in EXPENSE_CATEGORIES:
            result = await session.execute(select(ExpenseCategory).where(ExpenseCategory.name == cat["name"]))
            rows = result.all()
            if len(rows) == 0:
                session.add(ExpenseCategory(id=uuid.uuid4(), **cat, is_active=True))
                print(f"  + ExpenseCategory '{cat['name']}' created")
            else:
                print(f"  = ExpenseCategory '{cat['name']}' already exists")

        await session.flush()

        # Users + roles
        for u_data in USERS:
            result = await session.execute(select(User).where(User.login == u_data["login"]))
            user = result.scalar_one_or_none()

            if not user:
                pw_hash = bcrypt.hashpw(u_data["password"].encode(), bcrypt.gensalt()).decode()
                user = User(
                    id=uuid.uuid4(),
                    login=u_data["login"],
                    password_hash=pw_hash,
                    full_name=u_data["full_name"],
                    lang=UserLang(u_data["lang"]),
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                print(f"  + User '{u_data['login']}' created")
            else:
                print(f"  = User '{u_data['login']}' already exists")

            # Add roles if missing
            for role_name in u_data["roles"]:
                role_result = await session.execute(
                    select(UserRoleEntry).where(
                        UserRoleEntry.user_id == user.id,
                        UserRoleEntry.role == role_name,
                    )
                )
                if not role_result.scalar_one_or_none():
                    session.add(UserRoleEntry(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        role=role_name,
                    ))
                    print(f"    + Role '{role_name}' added to '{u_data['login']}'")
                else:
                    print(f"    = Role '{role_name}' already on '{u_data['login']}'")

        await session.commit()

    await engine.dispose()
    print("\nSeed completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_seed())
