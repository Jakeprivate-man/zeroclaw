"""Conversation Manager - Save/load conversations from filesystem.

This module provides persistent storage for conversations:
- Save conversations to JSON files
- Load conversations from disk
- List all saved conversations
- Delete conversations
- Manage conversation index
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid


class ConversationManager:
    """Manages conversation persistence to filesystem.

    Storage format:
        - Directory: ~/.zeroclaw/conversations/
        - Conversation files: {conversation_id}.json
        - Index file: conversations_index.json (metadata only)
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize conversation manager.

        Args:
            storage_dir: Custom storage directory (default: ~/.zeroclaw/conversations/)
        """
        if storage_dir:
            self.storage_dir = Path(storage_dir).expanduser()
        else:
            self.storage_dir = Path.home() / ".zeroclaw" / "conversations"

        # Ensure directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Index file path
        self.index_file = self.storage_dir / "conversations_index.json"

        # Load or create index
        self.index = self._load_index()

    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        """Load the conversation index from disk.

        Returns:
            Dict mapping conversation_id to metadata
        """
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading conversation index: {e}")
                return {}
        return {}

    def _save_index(self) -> None:
        """Save the conversation index to disk."""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving conversation index: {e}")

    def save_conversation(
        self,
        messages: List[Dict[str, Any]],
        title: Optional[str] = None,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """Save a conversation to disk.

        Args:
            messages: List of message dicts
            title: Conversation title (auto-generated if None)
            conversation_id: Existing ID to update (creates new if None)
            model: Model name used
            tags: List of tags

        Returns:
            Conversation ID
        """
        # Generate ID if new conversation
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # Generate title if not provided
        if not title:
            if messages:
                # Use first user message as title (truncated)
                first_user_msg = next(
                    (msg for msg in messages if msg.get('role') == 'user'),
                    None
                )
                if first_user_msg:
                    content = first_user_msg.get('content', '')
                    title = content[:50] + ("..." if len(content) > 50 else "")
                else:
                    title = "Untitled Conversation"
            else:
                title = "Empty Conversation"

        # Get timestamps
        now = datetime.now().timestamp()
        created = self.index.get(conversation_id, {}).get('created', now)

        # Create conversation object
        conversation = {
            "id": conversation_id,
            "title": title,
            "created": created,
            "modified": now,
            "messages": messages,
            "model": model or "unknown",
            "tags": tags or []
        }

        # Save conversation file
        conv_file = self.storage_dir / f"{conversation_id}.json"
        try:
            with open(conv_file, 'w', encoding='utf-8') as f:
                json.dump(conversation, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise IOError(f"Failed to save conversation: {e}")

        # Update index
        self.index[conversation_id] = {
            "id": conversation_id,
            "title": title,
            "created": created,
            "modified": now,
            "message_count": len(messages),
            "model": model or "unknown",
            "tags": tags or []
        }
        self._save_index()

        return conversation_id

    def load_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load a conversation from disk.

        Args:
            conversation_id: Conversation ID to load

        Returns:
            Conversation dict or None if not found
        """
        conv_file = self.storage_dir / f"{conversation_id}.json"

        if not conv_file.exists():
            return None

        try:
            with open(conv_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading conversation {conversation_id}: {e}")
            return None

    def list_conversations(
        self,
        sort_by: str = "modified",
        reverse: bool = True,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List all saved conversations (metadata only).

        Args:
            sort_by: Field to sort by ("created", "modified", "title")
            reverse: Sort in descending order (True) or ascending (False)
            limit: Maximum number of conversations to return

        Returns:
            List of conversation metadata dicts
        """
        conversations = list(self.index.values())

        # Sort
        if sort_by in ["created", "modified"]:
            conversations.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
        elif sort_by == "title":
            conversations.sort(key=lambda x: x.get('title', '').lower(), reverse=reverse)

        # Limit
        if limit:
            conversations = conversations[:limit]

        return conversations

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation.

        Args:
            conversation_id: Conversation ID to delete

        Returns:
            True if deleted, False if not found
        """
        conv_file = self.storage_dir / f"{conversation_id}.json"

        # Remove from index
        if conversation_id in self.index:
            del self.index[conversation_id]
            self._save_index()

        # Delete file
        if conv_file.exists():
            try:
                conv_file.unlink()
                return True
            except Exception as e:
                print(f"Error deleting conversation {conversation_id}: {e}")
                return False

        return False

    def get_storage_path(self) -> str:
        """Get the storage directory path.

        Returns:
            Absolute path to conversations directory
        """
        return str(self.storage_dir)

    def search_conversations(self, query: str) -> List[Dict[str, Any]]:
        """Search conversations by title or content.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching conversation metadata
        """
        query_lower = query.lower()
        results = []

        for conv_meta in self.index.values():
            # Check title
            if query_lower in conv_meta.get('title', '').lower():
                results.append(conv_meta)
                continue

            # Check tags
            tags = conv_meta.get('tags', [])
            if any(query_lower in tag.lower() for tag in tags):
                results.append(conv_meta)
                continue

            # Check content (load full conversation)
            conv_id = conv_meta.get('id')
            if conv_id:
                conversation = self.load_conversation(conv_id)
                if conversation:
                    messages = conversation.get('messages', [])
                    for msg in messages:
                        content = msg.get('content', '')
                        if query_lower in content.lower():
                            results.append(conv_meta)
                            break

        return results

    def export_conversation(
        self,
        conversation_id: str,
        format: str = "json"
    ) -> Optional[str]:
        """Export a conversation in specified format.

        Args:
            conversation_id: Conversation to export
            format: Export format ("json" or "markdown")

        Returns:
            Exported string or None if not found
        """
        conversation = self.load_conversation(conversation_id)

        if not conversation:
            return None

        if format == "json":
            return json.dumps(conversation, indent=2, ensure_ascii=False)

        elif format == "markdown":
            lines = [
                f"# {conversation.get('title', 'Untitled')}",
                "",
                f"**Created:** {datetime.fromtimestamp(conversation.get('created', 0)).strftime('%Y-%m-%d %H:%M:%S')}",
                f"**Modified:** {datetime.fromtimestamp(conversation.get('modified', 0)).strftime('%Y-%m-%d %H:%M:%S')}",
                f"**Model:** {conversation.get('model', 'unknown')}",
                "",
                "---",
                ""
            ]

            for msg in conversation.get('messages', []):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                timestamp = msg.get('timestamp', 0)

                time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S') if timestamp else 'Unknown'

                lines.append(f"## [{time_str}] {role.upper()}")
                lines.append("")
                lines.append(content)
                lines.append("")
                lines.append("---")
                lines.append("")

            return "\n".join(lines)

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored conversations.

        Returns:
            Dict with conversation statistics
        """
        total_conversations = len(self.index)
        total_messages = sum(meta.get('message_count', 0) for meta in self.index.values())

        models_used = {}
        for meta in self.index.values():
            model = meta.get('model', 'unknown')
            models_used[model] = models_used.get(model, 0) + 1

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "models_used": models_used,
            "storage_path": str(self.storage_dir)
        }
