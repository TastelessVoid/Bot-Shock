"""
Tests for permission checking utilities.
"""

import pytest
from unittest.mock import AsyncMock, Mock
import disnake

from botshock.utils.permissions import PermissionChecker


class TestPermissionChecker:
    """Test permission checking functionality."""

    def test_permission_checker_initialization(self, mock_database):
        """Test permission checker can be initialized."""
        checker = PermissionChecker(mock_database)
        assert checker.db is mock_database

    @pytest.mark.asyncio
    async def test_has_control_role_with_member_having_role(self):
        """Test checking control role when member has it."""
        mock_db = AsyncMock()
        mock_db.get_guild_control_roles = AsyncMock(return_value=[111, 222])
        
        checker = PermissionChecker(mock_db)
        
        # Create mock member with control role
        member = Mock(spec=disnake.Member)
        role1 = Mock()
        role1.id = 111
        member.roles = [role1]
        member.guild = Mock()
        member.guild.id = 12345
        
        result = await checker.has_control_role(member)
        assert result is True

    @pytest.mark.asyncio
    async def test_has_control_role_with_member_without_role(self):
        """Test checking control role when member doesn't have it."""
        mock_db = AsyncMock()
        mock_db.get_guild_control_roles = AsyncMock(return_value=[111, 222])
        
        checker = PermissionChecker(mock_db)
        
        # Create mock member without control role
        member = Mock(spec=disnake.Member)
        role1 = Mock()
        role1.id = 999
        member.roles = [role1]
        member.guild = Mock()
        member.guild.id = 12345
        
        result = await checker.has_control_role(member)
        assert result is False

    @pytest.mark.asyncio
    async def test_has_control_role_with_no_configured_roles(self):
        """Test checking control role when no roles are configured."""
        mock_db = AsyncMock()
        mock_db.get_guild_control_roles = AsyncMock(return_value=[])
        
        checker = PermissionChecker(mock_db)
        
        member = Mock(spec=disnake.Member)
        member.guild = Mock()
        member.guild.id = 12345
        member.roles = []
        
        result = await checker.has_control_role(member)
        assert result is False

    @pytest.mark.asyncio
    async def test_has_control_role_with_non_member_object(self):
        """Test checking control role with non-member object."""
        mock_db = AsyncMock()
        checker = PermissionChecker(mock_db)
        
        # Pass a non-member object
        result = await checker.has_control_role("not_a_member")
        assert result is False
        
        # Verify DB wasn't called
        mock_db.get_guild_control_roles.assert_not_called()

    def test_has_manage_roles_permission_with_permission(self):
        """Test checking manage roles permission when member has it."""
        member = Mock(spec=disnake.Member)
        perms = Mock()
        perms.administrator = False
        perms.manage_roles = True
        member.guild_permissions = perms
        
        result = PermissionChecker.has_manage_roles_permission(member)
        assert result is True

    def test_has_manage_roles_permission_with_admin(self):
        """Test checking manage roles permission with admin."""
        member = Mock(spec=disnake.Member)
        perms = Mock()
        perms.administrator = True
        perms.manage_roles = False
        member.guild_permissions = perms
        
        result = PermissionChecker.has_manage_roles_permission(member)
        assert result is True

    def test_has_manage_roles_permission_without_permission(self):
        """Test checking manage roles permission when member lacks it."""
        member = Mock(spec=disnake.Member)
        perms = Mock()
        perms.administrator = False
        perms.manage_roles = False
        member.guild_permissions = perms
        
        result = PermissionChecker.has_manage_roles_permission(member)
        assert result is False

    def test_has_manage_roles_permission_no_guild_permissions(self):
        """Test checking manage roles permission when guild_permissions is None."""
        member = Mock(spec=disnake.Member)
        member.guild_permissions = None
        
        result = PermissionChecker.has_manage_roles_permission(member)
        assert result is False

    @pytest.mark.asyncio
    async def test_can_manage_user_self_management(self):
        """Test user can always manage themselves."""
        mock_db = AsyncMock()
        checker = PermissionChecker(mock_db)
        
        executor = Mock(spec=disnake.Member)
        executor.id = 123
        target = Mock(spec=disnake.User)
        target.id = 123
        
        can_manage, reason = await checker.can_manage_user(executor, target)
        assert can_manage is True
        assert reason == "self"
        
        # DB should not be called for self-management
        mock_db.can_user_control.assert_not_called()

    @pytest.mark.asyncio
    async def test_can_manage_user_with_user_consent(self):
        """Test user can manage another user with explicit consent."""
        mock_db = AsyncMock()
        mock_db.can_user_control = AsyncMock(return_value=True)
        mock_db.get_controller_permissions = AsyncMock(
            return_value={"users": [456], "roles": []}
        )
        
        checker = PermissionChecker(mock_db)
        
        executor = Mock(spec=disnake.Member)
        executor.id = 456
        executor.guild = Mock()
        executor.guild.id = 999
        role1 = Mock()
        role1.id = 111
        executor.roles = [role1]
        
        target = Mock(spec=disnake.User)
        target.id = 123
        
        can_manage, reason = await checker.can_manage_user(executor, target)
        assert can_manage is True
        assert reason == "consent_user"

    @pytest.mark.asyncio
    async def test_can_manage_user_with_role_consent(self):
        """Test user can manage via role consent."""
        mock_db = AsyncMock()
        mock_db.can_user_control = AsyncMock(return_value=True)
        mock_db.get_controller_permissions = AsyncMock(
            return_value={"users": [], "roles": [111]}
        )
        
        checker = PermissionChecker(mock_db)
        
        executor = Mock(spec=disnake.Member)
        executor.id = 456
        executor.guild = Mock()
        executor.guild.id = 999
        role1 = Mock()
        role1.id = 111
        executor.roles = [role1]
        
        target = Mock(spec=disnake.User)
        target.id = 123
        
        can_manage, reason = await checker.can_manage_user(executor, target)
        assert can_manage is True
        assert reason == "consent_role"

    @pytest.mark.asyncio
    async def test_can_manage_user_without_consent(self):
        """Test user cannot manage without consent."""
        mock_db = AsyncMock()
        mock_db.can_user_control = AsyncMock(return_value=False)
        
        checker = PermissionChecker(mock_db)
        
        executor = Mock(spec=disnake.Member)
        executor.id = 456
        executor.guild = Mock()
        executor.guild.id = 999
        executor.roles = []
        
        target = Mock(spec=disnake.User)
        target.id = 123
        
        can_manage, reason = await checker.can_manage_user(executor, target)
        assert can_manage is False
        assert reason == "no_consent"

    @pytest.mark.asyncio
    async def test_can_manage_user_no_guild(self):
        """Test user cannot manage without guild context."""
        mock_db = AsyncMock()
        checker = PermissionChecker(mock_db)
        
        executor = Mock()
        executor.guild = None  # No guild
        target = Mock(spec=disnake.User)
        target.id = 123
        
        can_manage, reason = await checker.can_manage_user(executor, target, check_consent=True)
        assert can_manage is False
        assert reason == "no_guild"

