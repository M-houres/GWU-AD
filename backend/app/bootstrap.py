from app.main import assert_production_secrets, logger, run_runtime_bootstrap_tasks, settings


def main() -> None:
    assert_production_secrets()
    run_runtime_bootstrap_tasks()
    logger.info("bootstrap_completed", extra={"app_env": settings.app_env})


if __name__ == "__main__":
    main()
