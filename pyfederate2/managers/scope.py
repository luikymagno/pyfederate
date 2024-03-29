from typing import List
from abc import ABC, abstractmethod

from ..schemas.scope import ScopeIn, Scope


class ScopeManager(ABC):
    @abstractmethod
    async def create_scope(self, scope: ScopeIn) -> None:
        """
        Throws:
            EntityAlreadyExistsException
        """
        pass

    @abstractmethod
    async def update_scope(self, scope_name: str, scope: ScopeIn) -> None:
        """
        Throws:
            EntityDoesNotExistException
        """
        pass

    @abstractmethod
    async def get_scope(self, scope_name: str) -> Scope:
        """
        Throws:
            EntityDoesNotExistException
        """
        pass

    @abstractmethod
    async def get_scopes(self) -> List[Scope]:
        pass

    @abstractmethod
    async def delete_scope(self, scope_name: str) -> None:
        pass
