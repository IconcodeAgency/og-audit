import pytest

from og_audit.network import UnsafeTargetError, validate_public_url


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "http://169.254.169.254/latest/meta-data",
        "https://user:password@example.com",
    ],
)
async def test_blocks_unsafe_targets(url: str) -> None:
    with pytest.raises(UnsafeTargetError):
        await validate_public_url(url)


@pytest.mark.asyncio
async def test_private_target_can_be_explicitly_allowed() -> None:
    await validate_public_url("http://127.0.0.1:8000", allow_private=True)
