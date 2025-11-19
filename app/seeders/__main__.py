from .users import seed_users
from .dishes import seed_dishes
from .cooklogs import seed_cooklogs


def main():
    print("Running all seeders...")
    seed_users()
    seed_dishes()
    seed_cooklogs()
    print("Done seeding!")


if __name__ == "__main__":
    main()
