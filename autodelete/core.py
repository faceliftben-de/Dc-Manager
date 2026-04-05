"""
MIT License

Copyright (c) 2024-present japandotorg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import datetime
import io
import logging
from typing import Dict, Final, List, Literal, Optional, Union

import discord
from discord.ext import tasks
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import humanize_list

from .models import Transcript

log: logging.Logger = logging.getLogger("red.seina.autodelete")


class AutoDelete(commands.Cog):
    """
    Auto delete messages in specific channels.
    """

    __author__: Final[List[str]] = ["inthedark.org"]
    __version__: Final[str] = "0.1.0"

    def __init__(self, bot: Red) -> None:
        self.bot: Red = bot
        self.config: Config = Config.get_conf(self, identifier=69_420_666, force_registration=True)
        default_guild: Dict[str, Union[Dict[str, int], Optional[int], List[int]]] = {
            "channels": {},
            "log_channel": None,
            "ignore": [],
        }
        self.config.register_guild(**default_guild)

        self._auto_deleter.start()

    def format_help_for_context(self, ctx: commands.Context) -> str:
        pre_processed: str = super().format_help_for_context(ctx)
        n: str = "\n" if "\n\n" not in pre_processed else ""
        text = [
            f"{pre_processed}{n}",
            f"**Author:** {humanize_list(self.__author__)}",
            f"**Version:** {str(self.__version__)}",
        ]
        return "\n".join(text)

    @staticmethod
    async def _transcript(
        channel: discord.TextChannel, messages: List[discord.Message]
    ) -> Optional[str]:
        transcript: str = (
            await Transcript(
                channel=channel,
                messages=messages,
                pytz_timezone="UTC",
                military_time=True,
                fancy_times=True,
            ).export()
        ).html
        if not transcript:
            return
        return transcript

    async def cog_unload(self) -> None:
        self._auto_deleter.cancel()

    async def _log_messages(
        self,
        channel: discord.TextChannel,
        messages: List[discord.Message],
    ) -> None:
        log_channel: Optional[discord.TextChannel] = channel.guild.get_channel(
            await self.config.guild(channel.guild).log_channel()
        )  # type: ignore
        if not log_channel:
            return
        file: Optional[str] = await self._transcript(channel, messages)
        if not file:
            return
        date: datetime.date = datetime.date.today()
        await log_channel.send(
            f"Deleted **{len(messages)}** messages from {channel.mention}",
            file=discord.File(
                io.BytesIO(file.encode()),
                filename=f"{channel.name}-{date}.html",
            ),
        )

    @tasks.loop(minutes=60)
    async def _auto_deleter(self) -> None:
        await self.bot.wait_until_red_ready()
        config: Dict[int, Dict[str, Union[Dict[str, int], Optional[int], List[int]]]] = (
            await self.config.all_guilds()
        )
        for guild_id, guild_data in config.items():
            guild: Optional[discord.Guild] = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
            if not guild.me.guild_permissions.manage_messages:
                log.debug(
                    f" Ich kann {guild.name} ({guild.id}) nicht verwalten, da fehlende Berechtigungen vorliegen."
                )
                continue
            ignored_roles: List[int] = guild_data["ignore"]  # type: ignore

            def _ignored_role_check(message: discord.Message) -> bool:
                return not (
                    message.pinned
                    or (
                        isinstance(message.author, discord.Member)
                        and set(role.id for role in message.author.roles).intersection(
                            ignored_roles
                        )
                    )
                )

            channels: Dict[str, int] = guild_data["channels"]  # type: ignore
            for channel_id, days in channels.items():
                channel: Optional[discord.TextChannel] = guild.get_channel(int(channel_id))  # type: ignore
                if not channel:
                    continue
                try:
                    messages: List[discord.Message] = await channel.purge(
                        limit=None,
                        check=_ignored_role_check,
                        before=datetime.datetime.utcnow() - datetime.timedelta(days=days),
                    )
                except discord.HTTPException as error:
                    log.exception(
                        f"Ich kann Nachrichten in {channel.mention} nicht löschen, da fehlende Berechtigungen vorliegen.", exc_info=error
                    )
                    continue
                await self._log_messages(channel, messages)

    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.group(name="autodelete", aliases=["ad", "deleter"])
    async def _deleter(self, _: commands.GuildContext):
        """
        Konfiguriere Auto-Delete-Regeln für bestimmte Kanäle.
        """

    @_deleter.command(name="channels")  # type: ignore
    async def _channels(
        self,
        ctx: commands.GuildContext,
        add_or_remove: Literal["add", "remove"],
        channel: discord.TextChannel,
        days: Optional[commands.Range[int, 1, 13]] = None,
    ):
        """
        Füge Auto-Delete-Regeln für einen Kanal hinzu oder entferne sie. Beim Hinzufügen musst du die Anzahl der Tage angeben, nach denen Nachrichten gelöscht werden sollen. Beim Entfernen wird die Regel für den Kanal gelöscht.
        """
        channels: Dict[str, int] = await self.config.guild(ctx.guild).channels()
        if add_or_remove.lower() == "add":
            if days is None:
                raise commands.UserFeedbackCheckFailure(
                    "`Days` ist ein erforderliches Argument, das fehlt.",
                )
            if str(channel.id) in channels:
                raise commands.UserFeedbackCheckFailure(
                    f"{channel.mention} hat bereits eine Auto-Delete-Regel.",
                )
            channels[str(channel.id)] = days
            await self.config.guild(ctx.guild).channels.set(channels)
            await ctx.send(
                f"Füge Auto-Delete-Regel hinzu, um Nachrichten älter als {days} Tage aus {channel.mention} zu löschen.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
                allowed_mentions=discord.AllowedMentions(replied_user=False),
            )
        elif add_or_remove.lower() == "remove":
            if str(channel.id) not in channels:
                raise commands.UserFeedbackCheckFailure(
                    f"{channel.mention} hat keine Auto-Delete-Regel.",
                )
            del channels[str(channel.id)]
            await self.config.guild(ctx.guild).channels.set(channels)
            await ctx.send(
                f"Entferne Auto-Delete-Regel von {channel.mention}.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
                allowed_mentions=discord.AllowedMentions(replied_user=False),
            )
        else:
            await ctx.send_help(ctx.command)

    @_deleter.command(name="log", aliases=["logchannel"])  # type: ignore
    async def _log(
        self,
        ctx: commands.GuildContext,
        add_or_remove: Literal["add", "remove"],
        channel: Optional[discord.TextChannel] = None,
    ):
        """
        Füge Logging-Kanal für Auto-Delete-Regeln hinzu oder entferne ihn. Beim Hinzufügen musst du den Kanal angeben, in dem geloggt werden soll. Beim Entfernen wird der Logging-Kanal gelöscht.
        """
        if add_or_remove.lower() == "add":
            if channel is None:
                raise commands.UserFeedbackCheckFailure(
                    "`Channel` ist ein erforderliches Argument, das fehlt.",
                )
            await self.config.guild(ctx.guild).log_channel.set(channel.id)
            await ctx.send(
                f"Konfiguriere {channel.mention} als Logging-Kanal für Auto-Delete-Regeln.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
                allowed_mentions=discord.AllowedMentions(replied_user=False),
            )
        elif add_or_remove.lower() == "remove":
            await self.config.guild(ctx.guild).log_channel.clear()
            await ctx.send(
                f"Entferne Logging-Kanal für Auto-Delete-Regeln.",
                reference=ctx.message.to_reference(fail_if_not_exists=False),
                allowed_mentions=discord.AllowedMentions(replied_user=False),
            )
        else:
            await ctx.send_help(ctx.command)

    @_deleter.command(name="ignore", aliases=["ignorechannel"])  # type: ignore
    async def _ignore(
        self,
        ctx: commands.GuildContext,
        add_or_remove: Literal["add", "remove"],
        channels: commands.Greedy[discord.TextChannel],
    ):
        """
        Igoniere bestimmte Nutzer von der Funktion
        """
        async with self.config.guild(ctx.guild).ignore() as i:
            for channel in channels:
                if add_or_remove.lower() == "add":
                    if not channel.id in i:
                        i.append(channel.id)
                elif add_or_remove.lower() == "remove":
                    if channel.id in i:
                        i.remove(channel.id)
        await ctx.send(
            f"Erfolgreich {'hinzugefügt' if add_or_remove.lower() == 'add' else 'entfernt'} {len(channels)} Kanäle.",
            reference=ctx.message.to_reference(fail_if_not_exists=False),
            allowed_mentions=discord.AllowedMentions(replied_user=False),
        )
