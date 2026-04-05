import asyncio
import datetime
import logging
import random
from typing import Optional, Union

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box, humanize_list, pagify

from .enums import WhisperType
from .errors import WhisperError
from .safemodels import SafeGuild, SafeMember

__author__ = "tmerc"

log = logging.getLogger("red.tmerc.welcome")

ENABLED = "enabled"
DISABLED = "disabled"


class Welcome(commands.Cog):
    """Ankündigung von Mitgliedschaftsereignissen."""

    default_join = "Willkommen {member.mention} auf {server.name}!"
    default_leave = "{member.name} hat {server.name} verlassen!"
    default_ban = "{member.name} wurde von {server.name} gebannt!"
    default_unban = "{member.name} wurde von {server.name} entbannt!"
    default_whisper = "Heyy, {member.name}, willkommen auf {server.name}!"

    guild_defaults = {
        "enabled": False,
        "channel": None,
        "date": None,
        "join": {
            "enabled": True,
            "channel": None,
            "delete": False,
            "last": None,
            "counter": 0,
            "whisper": {"state": "off", "message": default_whisper},
            "messages": [default_join],
            "bot": None,
        },
        "leave": {
            "enabled": True,
            "channel": None,
            "delete": False,
            "last": None,
            "counter": 0,
            "messages": [default_leave],
        },
        "ban": {
            "enabled": True,
            "channel": None,
            "delete": False,
            "last": None,
            "counter": 0,
            "messages": [default_ban],
        },
        "unban": {
            "enabled": True,
            "channel": None,
            "delete": False,
            "last": None,
            "counter": 0,
            "messages": [default_unban],
        },
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.config = Config.get_conf(self, 86345009)
        self.config.register_guild(**self.guild_defaults)

    @commands.group(aliases=["welcomeset"], fallback="state")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def welcome(self, ctx: commands.Context) -> None:
        """Sehe aktuelle Willkommens-Einstellungen."""

        await ctx.typing()

        if ctx.invoked_subcommand is None:
            guild: discord.Guild = ctx.guild
            c = await self.config.guild(guild).all()

            channel = await self.__get_channel(guild, "default")
            join_channel = await self.__get_channel(guild, "join")
            leave_channel = await self.__get_channel(guild, "leave")
            ban_channel = await self.__get_channel(guild, "ban")
            unban_channel = await self.__get_channel(guild, "unban")

            j = c["join"]
            jw = j["whisper"]
            v = c["leave"]
            b = c["ban"]
            u = c["unban"]

            whisper_message = jw["message"] if len(jw["message"]) <= 50 else jw["message"][:50] + "..."

            if await ctx.embed_requested():
                emb = discord.Embed(color=await ctx.embed_color(), title="Current Welcome Settings")
                emb.add_field(
                    name="Allgeineine Einstellungen",
                    inline=False,
                    value=f"**Status:** {c['enabled']}\n**Kanal:** {channel.mention}\n",
                )
                emb.add_field(
                    name="Beitreten",
                    inline=False,
                    value=(
                        f"**Status:** {j['enabled']}\n"
                        f"**Kanal:** {join_channel.mention}\n"
                        f"**Vorherige löschen:** {j['delete']}\n"
                        f"**Whisper-Status:** {jw['state']}\n"
                        f"**Whisper-Nachricht:** {whisper_message}\n"
                        f"**Nachrichten:** {len(j['messages'])}; do `{ctx.prefix}welcomeset join msg list` für die Liste\n"
                        f"**Bot message:** {j['bot']}"
                    ),
                )
                emb.add_field(
                    name="Verlassen",
                    inline=False,
                    value=(
                        f"**Status:** {v['enabled']}\n"
                        f"**Kanal:** {leave_channel.mention}\n"
                        f"**Vorherige löschen:** {v['delete']}\n"
                        f"**Messages:** {len(v['messages'])}; do `{ctx.prefix}welcomeset leave msg list` für die Liste\n"
                    ),
                )
                emb.add_field(
                    name="Sperrungen",
                    inline=False,
                    value=(
                        f"**Status:** {b['enabled']}\n"
                        f"**Kanal:** {ban_channel.mention}\n"
                        f"**Vorherige löschen:** {b['delete']}\n"
                        f"**Messages:** {len(b['messages'])}; do `{ctx.prefix}welcomeset ban msg list` für die Liste\n"
                    ),
                )
                emb.add_field(
                    name="Entsperren",
                    inline=False,
                    value=(
                        f"**Status:** {u['enabled']}\n"
                        f"**Kanal:** {unban_channel.mention}\n"
                        f"**Vorherige löschen:** {u['delete']}\n"
                        f"**Messages:** {len(u['messages'])}; do `{ctx.prefix}welcomeset unban msg list` für die Liste\n"
                    ),
                )

                await ctx.send(embed=emb)
            else:
                msg = box(
                    f"  Status: {c['enabled']}\n"
                    f"  Kanal: {channel}\n"
                    f"  Join:\n"
                    f"    Status: {j['enabled']}\n"
                    f"    Kanal: {join_channel}\n"
                    f"    Vorherige löschen: {j['delete']}\n"
                    f"    Whisper:\n"
                    f"      Status: {jw['state']}\n"
                    f"      Nachricht: {whisper_message}\n"
                    f"    Nachrichten: {len(j['messages'])}; do '{ctx.prefix}welcomeset join msg list' für die Liste\n"
                    f"    Bot message: {j['bot']}\n"
                    f"  Leave:\n"
                    f"    Status: {v['enabled']}\n"
                    f"    Kanal: {leave_channel}\n"
                    f"    Vorherige löschen: {v['delete']}\n"
                    f"    Nachrichten: {len(v['messages'])}; do '{ctx.prefix}welcomeset leave msg list' für die Liste\n"
                    f"  Ban:\n"
                    f"    Status: {b['enabled']}\n"
                    f"    Kanal: {ban_channel}\n"
                    f"    Vorherige löschen: {b['delete']}\n"
                    f"    Nachrichten: {len(b['messages'])}; do '{ctx.prefix}welcomeset ban msg list' für die Liste\n"
                    f"  Unban:\n"
                    f"    Status: {u['enabled']}\n"
                    f"    Kanal: {unban_channel}\n"
                    f"    Vorherige löschen: {u['delete']}\n"
                    f"    Nachrichten: {len(u['messages'])}; do '{ctx.prefix}welcomeset unban msg list' für die Liste\n",
                    "Aktuelle Einstellungen",
                )

                await ctx.send(msg)

    @welcome.command(name="toggle")
    async def welcome_toggle(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviere die Willkommensnachrichten.

        Wenn `on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        guild = ctx.guild
        target_state = on_off if on_off is not None else not (await self.config.guild(guild).enabled())

        await self.config.guild(guild).enabled.set(target_state)

        await ctx.send(f"Willkommensnachrichten sind jetzt {ENABLED if target_state else DISABLED}.")

    @welcome.command(name="channel")
    async def welcome_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Sete einen Kanal für die Events."""

        if not Welcome.__can_speak_in(channel):
            await ctx.send(
                f"Ich kann in {channel.mention} keine Nachrichten senden. "
                "Überprüfe deine Berechtigungseinstellungen und versuche es erneut."
            )
            return

        guild = ctx.guild
        await self.config.guild(guild).channel.set(channel.id)

        await ctx.send(f"Ich werde jetzt Ereignisbenachrichtigungen an {channel.mention} senden.")

    @welcome.group(name="join")
    async def welcome_join(self, ctx: commands.Context) -> None:
        """Ändere die Einstellungen für Join-Nachrichten."""

        pass

    @welcome_join.command(name="toggle")
    async def welcome_join_toggle(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviere Join-Nachrichten.

        Wenn `on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        await self.__toggle(ctx, on_off, "join")

    @welcome_join.command(name="channel")
    async def welcome_join_channel(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        """Sete den Kanal für Join-Nachrichten.

        Wenn `channel` nicht angegeben ist, wird der join-spezifische Kanal gelöscht.
        """

        await self.__set_channel(ctx, channel, "join")

    @welcome_join.command(name="toggledelete")
    async def welcome_join_toggledelete(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviere das Löschen von vorherigen Join-Nachrichten.

        Wenn `on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        await self.__toggledelete(ctx, on_off, "join")

    @welcome_join.group(name="whisper")
    async def welcome_join_whisper(self, ctx: commands.Context) -> None:
        """Ändere die Einstellungen für Join-Whispers."""

        pass

    @welcome_join_whisper.command(name="type")
    async def welcome_join_whisper_type(self, ctx: commands.Context, choice: WhisperType) -> None:
        """Setze den Typ des Join-Whispers.

        Optionen sind:
          off - keine Whisper senden
          only - nur einen Whisper an das Mitglied senden, und keine Nachricht im Kanal
          both - sende einen Whisper an das Mitglied und eine Nachricht im Kanal
          fall - sende einen Whisper an das Mitglied, und wenn das fehlschlägt, sende eine Nachricht im Kanal
        """

        guild = ctx.guild
        whisper_type = choice.value
        channel = await self.__get_channel(ctx.guild, "join")

        await self.config.guild(guild).join.whisper.state.set(whisper_type)

        if choice == WhisperType.OFF:
            await ctx.send(f"Ich werde keine Whisper an neue Mitglieder senden, und werde eine Nachricht an {channel.mention} senden.")
        elif choice == WhisperType.ONLY:
            await ctx.send(f"Ich werde jetzt nur noch neue Mitglieder per DM kontaktieren, und werde keine Benachrichtigung an {channel.mention} senden.")
        elif choice == WhisperType.BOTH:
            await ctx.send(f"Ich werde jetzt sowohl neue Mitglieder per DM kontaktieren als auch eine Nachricht an {channel.mention} senden.")
        elif choice == WhisperType.FALLBACK:
            await ctx.send(
                f"Ich werde jetzt einen Whisper an neue Mitglieder senden, und wenn das fehlschlägt, werde ich die Nachricht an {channel.mention} senden."
            )

    @welcome_join_whisper.command(name="message", aliases=["msg"])
    async def welcome_join_whisper_message(self, ctx: commands.Context, *, msg_format: str) -> None:
        """Setze die Nachricht, die an neue Mitglieder gesendet wird.

        Erlaubt folgende Anpassungen:
          `{member}` das Mitglied
          `{server}` der Server
          `{count}` die Anzahl der Mitglieder, die heute beigetreten sind
        """

        await self.config.guild(ctx.guild).join.whisper.message.set(msg_format)

        await ctx.send("Ich werde jetzt diese Nachrichtenformat verwenden, wenn ich neue Mitglieder per Whisper kontaktiere, falls Whisper aktiviert ist.")

    @welcome_join.group(name="message", aliases=["msg"])
    async def welcome_join_message(self, ctx: commands.Context) -> None:
        """Verwalte das Willkommensnachrichten-Format."""

        pass

    @welcome_join_message.command(name="add")
    async def welcome_join_message_add(self, ctx: commands.Context, *, msg_format: str) -> None:
        """Füge ein neues Willkommensnachrichten-Format hinzu.

        Erlaubt folgende Anpassungen:
          `{member}` ist das neue Mitglied
          `{server}` ist der Server
          `{count}` ist die Anzahl der Mitglieder, die heute beigetreten sind
            `{plural}` ist ein 's', wenn `count` nicht 1 ist, und nichts, wenn es 1 ist
          `{roles}` ist eine Liste aller Rollen, die das Mitglied zum Zeitpunkt des Beitritts hat

        Zum Beispiel:
          {member.mention}... Was machst du denn hier???
          {server.name} hat ein neues Mitglied! {member.name}#{member.discriminator} - {member.id}
          Jemand ist beigetreten... Willkommen :D
        """

        await self.__message_add(ctx, msg_format, "join")

    @welcome_join_message.command(name="delete", aliases=["del"])
    async def welcome_join_message_delete(self, ctx: commands.Context) -> None:
        """Lösche ein bestehendes Willkommensnachrichten-Format aus der Liste."""

        await self.__message_delete(ctx, "join")

    @welcome_join_message.command(name="list", aliases=["ls"])
    async def welcome_join_message_list(self, ctx: commands.Context) -> None:
        """Listet die verfügbaren Willkommensnachrichten-Formate auf."""

        await self.__message_list(ctx, "join")

    @welcome_join.command(name="botmessage", aliases=["botmsg"])
    async def welcome_join_botmessage(self, ctx: commands.Context, *, msg_format: str = None) -> None:
        """Setze das Nachrichtenformat für Bot-Beitritte.

        Gib kein Format an, um normale Beitrittsnachrichten für Bots zu verwenden.
        Erlaubt folgende Anpassungen:
          `{bot}` ist der Bot
          `{server}` ist der Server
          `{count}` ist die Anzahl der Mitglieder, die heute beigetreten sind
          `{plural}` ist ein 's', wenn `count` nicht 1 ist, und nichts, wenn es 1 ist

        Zum Beispiel:
          {bot.mention} beep boop.
        """

        await self.config.guild(ctx.guild).join.bot.set(msg_format)

        if msg_format is not None:
            await ctx.send("Bot join Nachrichtenformat gesetzt. Ich werde jetzt Bots mit dieser Nachricht begrüßen.")
        else:
            await ctx.send("Bot join Nachrichtenformat entfernt. Ich werde jetzt Bots wie normale Mitglieder begrüßen.")

    @welcome.group(name="leave")
    async def welcome_leave(self, ctx: commands.Context) -> None:
        """Verwalte Verlassnachrichten."""

        pass

    @welcome_leave.command(name="toggle")
    async def welcome_leave_toggle(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviere Verlassnachrichten.

        Wenn`on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        await self.__toggle(ctx, on_off, "leave")

    @welcome_leave.command(name="channel")
    async def welcome_leave_channel(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        """Setze den Kanal, der speziell für Verlassnachrichten verwendet werden soll.

        Wenn `channel` nicht angegeben ist, wird der Verlass-spezifische Kanal gelöscht.
        """

        await self.__set_channel(ctx, channel, "leave")

    @welcome_leave.command(name="toggledelete")
    async def welcome_leave_toggledelete(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviert das Löschen vorheriger Verlassnachrichten.

        Wenn `on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        await self.__toggledelete(ctx, on_off, "leave")

    @welcome_leave.group(name="message", aliases=["msg"])
    async def welcome_leave_message(self, ctx: commands.Context) -> None:
        """Verwalte Verlassnachrichten-Formate."""

        pass

    @welcome_leave_message.command(name="add")
    async def welcome_leave_message_add(self, ctx: commands.Context, *, msg_format: str) -> None:
        """Füge ein neues Verlassnachrichten-Format hinzu.

        Erlaubt folgende Anpassungen:
          `{member}` ist das Mitglied, das den Server verlassen hat
          `{server}` ist der Server
          `{count}` ist die Anzahl der Mitglieder, die heute den Server verlassen haben
          `{plural}` ist ein 's', wenn `count` nicht 1 ist, und nichts, wenn es 1 ist
          `{roles}` ist eine Liste aller Rollen, die das Mitglied zur Zeit hat

        Zum Beispiel:
          {member.name}... Wieso hast du den Server verlassen???
          {server.name} hat ein Mitglied verloren! {member.name}#{member.discriminator} - {member.id}
          Jemand hat den Server verlassen... Oww... Auf Wiedersehen :(
        """

        await self.__message_add(ctx, msg_format, "leave")

    @welcome_leave_message.command(name="delete", aliases=["del"])
    async def welcome_leave_message_delete(self, ctx: commands.Context) -> None:
        """Lösche ein bestehendes Verlassnachrichten-Format aus der Liste."""

        await self.__message_delete(ctx, "leave")

    @welcome_leave_message.command(name="list", aliases=["ls"])
    async def welcome_leave_message_list(self, ctx: commands.Context) -> None:
        """Listet die verfügbaren Verlassnachrichten-Formate auf."""

        await self.__message_list(ctx, "leave")

    @welcome.group(name="ban")
    async def welcome_ban(self, ctx: commands.Context) -> None:
        """Verwalte Verbannungsnachrichten."""

        pass

    @welcome_ban.command(name="toggle")
    async def welcome_ban_toggle(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviert Verbannungsnachrichten.

        Wenn `on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        await self.__toggle(ctx, on_off, "ban")

    @welcome_ban.command(name="channel")
    async def welcome_ban_channel(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        """Setze den Kanal, der speziell für Verbannungsnachrichten verwendet werden soll.

        Wenn `channel` nicht angegeben ist, wird der Verbannungsspezifische Kanal gelöscht.
        """

        await self.__set_channel(ctx, channel, "ban")

    @welcome_ban.command(name="toggledelete")
    async def welcome_ban_toggledelete(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviert das Löschen vorheriger Verbannungsnachrichten.

        Wenn `on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        await self.__toggledelete(ctx, on_off, "ban")

    @welcome_ban.group(name="message", aliases=["msg"])
    async def welcome_ban_message(self, ctx: commands.Context) -> None:
        """Verwalte Verbannungsnachrichten-Formate."""

        pass

    @welcome_ban_message.command(name="add")
    async def welcome_ban_message_add(self, ctx: commands.Context, *, msg_format: str) -> None:
        """Füge ein neues Verbannungsnachrichten-Format hinzu.

        Erlaubt folgende Anpassungen:
          `{member}` ist das verbannte Mitglied
          `{server}` ist der Server
          `{count}` ist die Anzahl der Mitglieder, die heute verbannt wurden
          `{plural}` ist ein 's', wenn `count` nicht 1 ist, und nichts, wenn es 1 ist
          `{roles}` ist eine Liste aller Rollen, die das Mitglied zur Zeit hat

        Zum Beispiel:
          {member.name} wurde gesperrt... Hast du etwas falsch gemacht???
          Ein Mitglied des {server.name} wurde verbannt! {member.name}#{member.discriminator} - {member.id}
         Jemand wurde verbannt! :(
        """

        await self.__message_add(ctx, msg_format, "ban")

    @welcome_ban_message.command(name="delete", aliases=["del"])
    async def welcome_ban_message_delete(self, ctx: commands.Context) -> None:
        """Lösche ein bestehendes Verbannungsnachrichten-Format aus der Liste."""

        await self.__message_delete(ctx, "ban")

    @welcome_ban_message.command(name="list", aliases=["ls"])
    async def welcome_ban_message_list(self, ctx: commands.Context) -> None:
        """Listet die verfügbaren Verbannungsnachrichten-Formate auf."""

        await self.__message_list(ctx, "ban")

    @welcome.group(name="unban")
    async def welcome_unban(self, ctx: commands.Context) -> None:
        """Verwalte Entbannungsnachrichten."""

        pass

    @welcome_unban.command(name="toggle")
    async def welcome_unban_toggle(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviert Entbannungsnachrichten.

        Wenn `on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        await self.__toggle(ctx, on_off, "unban")

    @welcome_unban.command(name="channel")
    async def welcome_unban_channel(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        """Setze den Kanal, der speziell für Entbannungsnachrichten verwendet werden soll.

        Wenn `channel` nicht angegeben ist, wird der Entbannungsspezifische Kanal gelöscht.
        """

        await self.__set_channel(ctx, channel, "unban")

    @welcome_unban.command(name="toggledelete")
    async def welcome_unban_toggledelete(self, ctx: commands.Context, on_off: bool = None) -> None:
        """Aktiviert oder deaktiviert das Löschen vorheriger Entbannungsnachrichten.

        Wenn `on_off` nicht angegeben ist, wird der Status umgeschaltet.
        """

        await self.__toggledelete(ctx, on_off, "unban")

    @welcome_unban.group(name="message", aliases=["msg"])
    async def welcome_unban_message(self, ctx: commands.Context) -> None:
        """Verwalte Entbannungsnachrichten-Formate."""

        pass

    @welcome_unban_message.command(name="add")
    async def welcome_unban_message_add(self, ctx: commands.Context, *, msg_format: str) -> None:
        """Füge ein neues Entbannungsnachrichten-Format hinzu.

        Erlaubt folgende Anpassungen:
          `{member}` ist das entbannte Mitglied
          `{server}` ist der Server
          `{count}` ist die Anzahl der Mitglieder, die heute entbannt wurden
          `{plural}` ist ein 's', wenn `count` nicht 1 ist, und nichts, wenn es 1 ist
          `{roles}` ist eine Liste aller Rollen, die das Mitglied zur Zeit hat

        Zum Beispiel:
          {member.name} wurde entbannt... Hast du etwas falsch gemacht???
          Ein Mitglied des {server.name} wurde entbannt! {member.name}#{member.discriminator} - {member.id}
          Jemand wurde entbannt. Verschwende deine zweite Chance!
        """

        await self.__message_add(ctx, msg_format, "unban")

    @welcome_unban_message.command(name="delete", aliases=["del"])
    async def welcome_unban_message_delete(self, ctx: commands.Context) -> None:
        """Löscht ein vorhandenes Entbannungsnachrichten-Format aus der Liste."""

        await self.__message_delete(ctx, "unban")

    @welcome_unban_message.command(name="list", aliases=["ls"])
    async def welcome_unban_message_list(self, ctx: commands.Context) -> None:
        """Listet die verfügbaren Entbannungsnachrichten-Formate auf."""

        await self.__message_list(ctx, "unban")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Listen von member joins."""

        guild: discord.Guild = member.guild
        guild_settings = self.config.guild(guild)

        if await guild_settings.enabled() and await guild_settings.join.enabled():
            # join notice should be sent
            message_format: Optional[str] = None
            if member.bot:
                # bot
                message_format = await guild_settings.join.bot()

            else:
                whisper_type: str = await guild_settings.join.whisper.state()
                if whisper_type != "off":
                    try:
                        await self.__dm_user(member)
                    except WhisperError:
                        if whisper_type == "fall":
                            message_format = await self.config.guild(member.guild).join.whisper.message()
                            await self.__handle_event(guild, member, "join", message_format=message_format)
                            return

                    if whisper_type == "only" or whisper_type == "fall":
                        # we're done here
                        return

            await self.__handle_event(guild, member, "join", message_format=message_format)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Listen von Member Leaves."""

        await self.__handle_event(member.guild, member, "leave")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, member: discord.Member) -> None:
        """Listen von user bans."""

        await self.__handle_event(guild, member, "ban")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        """Listens for user unbans."""

        await self.__handle_event(guild, user, "unban")

    #
    # concrete handlers for settings changes and events
    #

    async def __toggle(self, ctx: commands.Context, on_off: bool, event: str) -> None:
        """Handler for setting toggles."""

        guild: discord.Guild = ctx.guild
        target_state = on_off if on_off is not None else not (await self.config.guild(guild).get_attr(event).enabled())

        await self.config.guild(guild).get_attr(event).enabled.set(target_state)

        await ctx.send(f"{event.capitalize()} notices are now {ENABLED if target_state else DISABLED}.")

    async def __set_channel(self, ctx: commands.Context, channel: discord.TextChannel, event: str) -> None:
        """Handler for setting channels."""

        guild: discord.Guild = ctx.guild

        store_this = channel.id if channel is not None else None

        await self.config.guild(guild).get_attr(event).channel.set(store_this)

        if store_this is not None:
            await ctx.send(f"Ich werde {event} benachrichtigungen an {channel.mention} senden.")
        else:
            default_channel = await self.__get_channel(guild, "default")
            await ctx.send(f"Ich werde {event} benachrichtigungen an den Standardkanal, {default_channel.mention}, senden.")

    async def __toggledelete(self, ctx: commands.Context, on_off: bool, event: str) -> None:
        """Handler for setting delete toggles."""

        guild: discord.Guild = ctx.guild
        target_state = on_off if on_off is not None else not (await self.config.guild(guild).get_attr(event).delete())

        await self.config.guild(guild).get_attr(event).delete.set(target_state)

        await ctx.send(f"Das Löschen der vorherigen {event} Benachrichtigung ist jetzt {ENABLED if target_state else DISABLED}")

    async def __message_add(self, ctx: commands.Context, msg_format: str, event: str) -> None:
        """Handler for adding message formats."""

        guild: discord.Guild = ctx.guild

        async with self.config.guild(guild).get_attr(event).messages() as messages:
            messages.append(msg_format)

        await ctx.send(f"Neue {event} Benachrichtigung hinzugefügt.")

    async def __message_delete(self, ctx: commands.Context, event: str) -> None:
        """Handler for deleting message formats."""

        guild: discord.Guild = ctx.guild

        async with self.config.guild(guild).get_attr(event).messages() as messages:
            if len(messages) == 1:
                await ctx.send(f"Ich habe nur ein {event} Nachrichtenformat, daher kann ich es nicht löschen.")
                return

            await self.__message_list(ctx, event)
            await ctx.send(f"Bitte geben Sie die Nummer des {event} Nachrichtenformats ein, das Sie löschen möchten.")

            try:
                num = await Welcome.__get_number_input(ctx, len(messages))
            except asyncio.TimeoutError:
                await ctx.send(f"Okay, Ich kann nix von {event} löschen.")
                return
            else:
                removed = messages.pop(num - 1)

        await ctx.send(f"Fertig. Dieses {event} Nachrichtenformat wurde gelöscht:\n`{removed}`")

    async def __message_list(self, ctx: commands.Context, event: str) -> None:
        """Handler for listing message formats."""

        guild: discord.Guild = ctx.guild

        msg = f"{event.capitalize()} message formats:\n"
        messages = await self.config.guild(guild).get_attr(event).messages()
        for n, m in enumerate(messages, start=1):
            msg += f"  {n}. {m}\n"

        for page in pagify(msg, shorten_by=20):
            await ctx.send(box(page))

    async def __handle_event(
        self, guild: discord.guild, user: Union[discord.Member, discord.User], event: str, *, message_format=None
    ) -> None:
        """Handler for actual events."""

        guild_settings = self.config.guild(guild)

        # always increment, even if we aren't sending a notice
        await self.__increment_count(guild, event)

        if await guild_settings.enabled():
            settings = await guild_settings.get_attr(event).all()
            if settings["enabled"]:
                # notices for this event are enabled

                if settings["delete"] and settings["last"] is not None:
                    # we need to delete the previous message
                    await self.__delete_message(guild, settings["last"], event)
                    # regardless of success, remove reference to that message
                    await guild_settings.get_attr(event).last.set(None)

                # send a notice to the channel
                new_message = await self.__send_notice(guild, user, event, message_format=message_format)
                # store it for (possible) deletion later
                await guild_settings.get_attr(event).last.set(new_message and new_message.id)

    async def __get_channel(self, guild: discord.Guild, event: str) -> discord.TextChannel:
        """Gets the best text channel to use for event notices.

        Order of priority:
        1. User-defined channel
        2. Guild's system channel (if bot can speak in it)
        3. First channel that the bot can speak in
        """

        channel = None

        if event == "default":
            channel_id: int = await self.config.guild(guild).channel()
        else:
            channel_id = await self.config.guild(guild).get_attr(event).channel()

        if channel_id is not None:
            channel = guild.get_channel(channel_id)

        if channel is None or not Welcome.__can_speak_in(channel):
            channel = guild.get_channel(await self.config.guild(guild).channel())

        if channel is None or not Welcome.__can_speak_in(channel):
            channel = guild.system_channel

        if channel is None or not Welcome.__can_speak_in(channel):
            for ch in guild.text_channels:
                if Welcome.__can_speak_in(ch):
                    channel = ch
                    break

        return channel

    async def __delete_message(self, guild: discord.Guild, message_id: int, event: str) -> None:
        """Attempts to delete the message with the given ID."""

        try:
            await (await (await self.__get_channel(guild, event)).fetch_message(message_id)).delete()
        except discord.NotFound:
            log.warning("Failed to delete message (ID {message_id}): not found")
        except discord.Forbidden:
            log.warning("Failed to delete message (ID {message_id}): insufficient permissions")
        except discord.DiscordException:
            log.warning("Failed to delete message (ID {message_id})")

    async def __send_notice(
        self, guild: discord.guild, user: Union[discord.Member, discord.User], event: str, *, message_format=None
    ) -> Optional[discord.Message]:
        """Sends the notice for the event."""

        format_str = message_format or await self.__get_random_message_format(guild, event)

        count = await self.config.guild(guild).get_attr(event).counter()
        plural = ""
        if count and count != 1:
            plural = "s"

        channel = await self.__get_channel(guild, event)

        role_str: str = ""
        if isinstance(user, discord.Member):
            roles = [r.name for r in user.roles if r.name != "@everyone"]
            if len(roles) > 0:
                role_str = humanize_list(roles)

        try:
            return await channel.send(
                format_str.format(
                    member=SafeMember(user),
                    server=SafeGuild(guild),
                    bot=SafeMember(user),
                    count=count or "",
                    plural=plural,
                    roles=role_str,
                )
            )
        except discord.Forbidden:
            log.error(
                f"Failed to send {event} message to channel ID {channel.id} (server ID {guild.id}): "
                "insufficient permissions"
            )
            return None
        except discord.DiscordException:
            log.error(f"Failed to send {event} message to channel ID {channel.id} (server ID {guild.id})")
            return None

    async def __get_random_message_format(self, guild: discord.guild, event: str) -> str:
        """Gets a random message for event of type event."""

        async with self.config.guild(guild).get_attr(event).messages() as messages:
            return random.choice(messages)

    async def __increment_count(self, guild: discord.Guild, event: str) -> None:
        """Increments the counter for <event>s today. Handles date changes."""

        guild_settings = self.config.guild(guild)

        if await guild_settings.date() is None:
            await guild_settings.date.set(Welcome.__today())

        if Welcome.__today() > await guild_settings.date():
            await guild_settings.date.set(Welcome.__today())
            await guild_settings.get_attr(event).counter.set(0)

        count: int = await guild_settings.get_attr(event).counter()
        await guild_settings.get_attr(event).counter.set(count + 1)

    async def __dm_user(self, member: discord.Member) -> None:
        """Sends a DM to the user with a filled-in message_format."""

        message_format = await self.config.guild(member.guild).join.whisper.message()

        try:
            await member.send(message_format.format(member=member, server=member.guild))
        except discord.Forbidden:
            log.error(
                f"Failed to send DM to member ID {member.id} (server ID {member.guild.id}): insufficient permissions"
            )
            raise WhisperError()
        except discord.DiscordException:
            log.error(f"Failed to send DM to member ID {member.id} (server ID {member.guild.id})")
            raise WhisperError()

    @staticmethod
    async def __get_number_input(ctx: commands.Context, maximum: int, minimum: int = 0) -> int:
        """Gets a number from the user, minimum < x <= maximum."""

        author = ctx.author
        channel = ctx.channel

        def check(m: discord.Message) -> bool:
            try:
                num = int(m.content)
            except ValueError:
                return False

            return num is not None and minimum < num <= maximum and m.author == author and m.channel == channel

        try:
            msg = await ctx.bot.wait_for("message", check=check, timeout=15.0)
        except asyncio.TimeoutError:
            raise
        else:
            return int(msg.content)

    @staticmethod
    def __can_speak_in(channel: discord.TextChannel) -> bool:
        """Indicates whether the bot has permission to speak in channel."""

        return channel.permissions_for(channel.guild.me).send_messages

    @staticmethod
    def __today() -> int:
        """Gets today's date in ordinal form."""

        return datetime.date.today().toordinal()
