from __future__ import annotations

import asyncio
import json

from app.core.container import get_container


async def main() -> None:
    container = get_container()
    loader = container.normalization_profile_loader()

    redis_loaded = await loader.load_profiles_to_redis()
    mongo_loaded = await loader.load_profiles_to_mongo()
    status = await loader.get_storage_status()

    print("=== BOOTSTRAP NORMALIZATION PROFILES ===")
    print(f"redis_loaded={redis_loaded}")
    print(f"mongo_loaded={mongo_loaded}")
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
