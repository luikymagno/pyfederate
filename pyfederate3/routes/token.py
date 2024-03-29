from typing import Annotated, List
from fastapi import Path, APIRouter, status

from ..schemas.token import TokenModelIn, TokenModelOut
from ..crud.auth import AuthCRUDManager

router = APIRouter(tags=["management"])
auth_manager = AuthCRUDManager()


@router.post(
    "/token-model",
    status_code=status.HTTP_201_CREATED,
)
async def create_token_model(
    token_model_input: TokenModelIn,
) -> None:
    await auth_manager.token_model_manager.create_token_model(token_model=token_model_input)


@router.put(
    "/token-model/{id}",
    status_code=status.HTTP_200_OK,
)
async def update_token_model(
    token_model_id: Annotated[str, Path(alias="id")],
    token_model_input: TokenModelIn,
) -> None:
    await auth_manager.token_model_manager.update_token_model(
        token_model_id=token_model_id, token_model=token_model_input
    )


@router.get(
    "/token-model/{id}",
    status_code=status.HTTP_200_OK,
)
async def get_token_model(
    token_model_id: Annotated[str, Path(alias="id")]
) -> TokenModelOut:
    return await auth_manager.token_model_manager.get_token_model_out(token_model_id=token_model_id)


@router.get(
    "/token-models",
    status_code=status.HTTP_200_OK,
)
async def get_token_models() -> List[TokenModelOut]:
    return await auth_manager.token_model_manager.get_token_models_out()


@router.delete(
    "/token-model/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_token_model(
    token_model_id: Annotated[str, Path(alias="id")],
) -> None:
    await auth_manager.token_model_manager.delete_token_model(token_model_id=token_model_id)
