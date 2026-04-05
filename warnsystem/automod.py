import discord
import asyncio

from redbot.core import commands
from redbot.core import checks
from redbot.core.i18n import Translator
from redbot.core.utils import menus
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate
from redbot.core.utils.chat_formatting import pagify, box
from redbot.core.commands.converter import TimedeltaConverter

from typing import Optional
from datetime import timedelta

from .abc import MixinMeta
from .converters import ValidRegex

_ = Translator("WarnSystem", __file__)


class AutomodMixin(MixinMeta):
    """
    Automod Konfiguration.
    """

    async def _ask_for_value(
        self,
        ctx: commands.Context,
        bot_msg: discord.Message,
        embed: discord.Embed,
        description: str,
        need: str = "same_context",
        optional: bool = False,
    ):
        embed.description = description
        if optional:
            embed.set_footer(text=_('\n\nSchreibe "skip" um diesen Parameter wegzulassen.'))
        await bot_msg.edit(content="", embed=embed)
        pred = getattr(MessagePredicate, need, MessagePredicate.same_context)(ctx)
        user_msg = await self.bot.wait_for("message", check=pred, timeout=30)
        if ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            await user_msg.delete()
        if optional and user_msg.content == "skip":
            return None
        if need == "time":
            try:
                time = await TimedeltaConverter().convert(ctx, user_msg.content)
            except commands.BadArgument:
                await ctx.send(_("Ungültiges Zeitformat."))
                return await self._ask_for_value(ctx, bot_msg, embed, description, need, optional)
            else:
                return time
        if need == "same_context":
            return user_msg.content
        return pred.result

    def _format_embed_for_autowarn(
        self,
        embed: discord.Embed,
        number_of_warns: int,
        warn_level: int,
        warn_reason: str,
        lock_level: int,
        only_automod: bool,
        time: timedelta,
        duration: timedelta,
    ) -> discord.Embed:
        time_str = _("Nicht gesetzt.") if not time else self.api._format_timedelta(time)
        duration_str = _("Nicht gesetzt.") if not duration else self.api._format_timedelta(duration)
        embed.description = _("Anzahl an Warnungen bis zur Aktion: {num}\n").format(
            num=number_of_warns
        )
        embed.description += _("Warnstufe: {level}\n").format(level=warn_level)
        embed.description += _("Warngrund: {reason}\n").format(reason=warn_reason)
        embed.description += _("Time interval: {time}\n").format(time=time_str)
        if warn_level == 2 or warn_level == 5:
            embed.description += _("Dauer: {time}\n").format(time=duration_str)
        embed.description += _("Lock to level: {level}\n").format(
            level=_("disabled") if lock_level == 0 else lock_level
        )
        embed.description += _("Nur Automod zählen: {enabled}\n\n").format(
            enabled=_("ja") if only_automod else _("nein")
        )
        embed.add_field(
            name=_("Was passiert:"),
            value=_(
                "Wenn ein Mitglied {number}{level_lock} warnings{from_bot}{within_time} erhält, wird der Bot ihm eine Warnung der Stufe {level} erteilen{duration} aus dem Grund: {reason}"
            ).format(
                number=number_of_warns,
                level_lock=_(" level {level}").format(level=lock_level) if lock_level else "",
                from_bot=_(" from the automod") if only_automod else "",
                within_time=_(" within {time}").format(time=time_str) if time else "",
                level=warn_level,
                duration=_(" during {time}").format(time=duration_str) if duration else "",
                reason=warn_reason,
            ),
            inline=False,
        )
        return embed

    @commands.group(name="wautomod")
    @checks.admin_or_permissions(administrator=True)
    async def automod(self, ctx: commands.Context):
        """
        WarnSystem Automod Konfiguration.
        """
        pass

    @automod.command(name="enable")
    async def automod_enable(self, ctx: commands.Context, confirm: bool = None):
        """
        Aktiviere oder deaktiviere das WarnSystem's Automod.
        """
        guild = ctx.guild
        if confirm is not None:
            if confirm:
                if not self.cache.automod_enabled:
                    self.api.enable_automod()
                await self.cache.add_automod_enabled(guild)
                await ctx.send(_("Automod ist jetzt aktiviert."))
            else:
                await self.cache.remove_automod_enabled(guild)
                if not self.cache.automod_enabled:
                    self.api.disable_automod()
                await ctx.send(_("Automod ist jetzt deaktiviert."))
        else:
            current = await self.data.guild(guild).automod.enabled()
            await ctx.send(
                _(
                    "Automod ist momentan auf {state}.\n"
                    "Type `{prefix}automod enable {arg}` um {action} es."
                ).format(
                    state=_("enabled") if current else _("disabled"),
                    prefix=ctx.clean_prefix,
                    arg=not current,
                    action=_("aktivieren") if not current else _("deaktivieren"),
                )
            )

    @automod.group(name="regex")
    async def automod_regex(self, ctx: commands.Context):
        """
        Trigger Warnungen basierend auf regulären Ausdrücken.
        """
        pass

    @automod_regex.command(name="add")
    async def automod_regex_add(
        self,
        ctx: commands.Context,
        name: str,
        regex: ValidRegex,
        level: int,
        time: Optional[TimedeltaConverter],
        *,
        reason: str,
    ):
        """
        Erstelle einen neuen Regex-Trigger für eine Warnung.

        Verwende https://regex101.com/ um deinen Ausdruck zu testen.

        Mögliche Keywords:
        - `{member}`
        - `{channel}`
        - `{guild}`

        Beispiel: `[p]automod regex add discord_invite \
"(?i)(discord\\.gg|discordapp\\.com\\/invite|discord\\.me)\\/(\\S+)" \
1 Discord invite sent in {channel.mention}.`
        """
        guild = ctx.guild
        automod_regex = await self.cache.get_automod_regex(guild)
        if name in automod_regex:
            await ctx.send(_("Der Name ist bereits vergeben."))
            return
        if time:
            if level == 2 or level == 5:
                time = time.total_seconds()
            else:
                time = None
        await self.cache.add_automod_regex(guild, name, regex, level, time, reason)
        await ctx.send(_("Regex-Trigger hinzugefügt!"))

    @automod_regex.command(name="delete", aliases=["del", "remove"])
    async def automod_regex_delete(self, ctx: commands.Context, name: str):
        """
        Lösche einen Regex trigger.
        """
        guild = ctx.guild
        if name not in await self.cache.get_automod_regex(guild):
            await ctx.send(_("Der Regex-Trigger existiert nicht."))
            return
        await self.cache.remove_automod_regex(guild, name)
        await ctx.send(_("Regex-Trigger entfernt."))

    @automod_regex.command(name="list")
    async def automod_regex_list(self, ctx: commands.Context):
        """
        Liste alle Regex-Triggers auf.
        """
        guild = ctx.guild
        automod_regex = await self.cache.get_automod_regex(guild)
        text = ""
        if not automod_regex:
            await ctx.send(_("Keine Regex-Triggers registriert."))
            return
        for name, value in automod_regex.items():
            text += (
                f"+ {name}\nLevel {value['level']} warning. Grund: {value['reason'][:40]}...\n\n"
            )
        messages = []
        pages = list(pagify(text, delims=["\n\n", "\n"], priority=True, page_length=1900))
        for i, page in enumerate(pages):
            messages.append(
                _("Page {i}/{total}").format(i=i + 1, total=len(pages)) + box(page, "diff")
            )
        await menus.menu(ctx, pages=messages, controls=menus.DEFAULT_CONTROLS)

    @automod_regex.command(name="show")
    async def automod_regex_show(self, ctx: commands.Context, name: str):
        """
        Zeige Details eines Regex-Triggers an.
        """
        guild = ctx.guild
        try:
            automod_regex = (await self.cache.get_automod_regex(guild))[name]
        except KeyError:
            await ctx.send(_("Der Regex-Trigger existiert nicht."))
            return
        embed = discord.Embed(title=_("Regex trigger: {name}").format(name=name))
        embed.description = _("Regex-Trigger Details.")
        embed.add_field(
            name=_("Regular expression"), value=box(automod_regex["regex"].pattern), inline=False
        )
        embed.add_field(
            name=_("Verwarnung"),
            value=_("**Level:** {level}\n**Grund:** {reason}\n**Dauer:** {time}").format(
                level=automod_regex["level"],
                reason=automod_regex["reason"],
                time=self.api._format_timedelta(automod_regex["time"])
                if automod_regex["time"]
                else _("."),
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @automod_regex.command(name="edited")
    async def automod_regex_edited(self, ctx: commands.Context, enable: bool = None):
        """
        Definiere, ob der Automod auch bearbeitete Nachrichten überprüfen soll.
        """
        guild = ctx.guild
        if enable is not None:
            if enable is True:
                await self.cache.set_automod_regex_edited(guild, True)
                await ctx.send(_("Der Automod überprüft nun auch bearbeitete Nachrichten."))
            else:
                await self.cache.set_automod_regex_edited(guild, False)
                await ctx.send(_("Der Automod überprüft nun nicht mehr bearbeitete Nachrichten."))
        else:
            current = await self.data.guild(guild).automod.regex_edited_messages()
            await ctx.send(
                _(
                    "Bearbeitete Nachrichtenüberprüfung ist derzeit {state}.\n"
                    "Nutze `{prefix}automod regex edited {arg}` um sie zu {action}."
                ).format(
                    state=_("enabled") if current else _("disabled"),
                    prefix=ctx.clean_prefix,
                    arg=not current,
                    action=_("enable") if not current else _("disable"),
                )
            )

    @automod.group(name="warn")
    async def automod_warn(self, ctx: commands.Context):
        """
        Konfiguriere automatische Verwarnungen basierend auf der Anzahl an Warnungen eines Mitglieds.

        Zum Beispiel, wenn ein Mitglied 3 Warnungen innerhalb eines Tages erhält, kannst du den Bot so konfigurieren, dass er automatisch eine Stufe-3-Warnung mit dem gegebenen Grund setzt.
        Es ist auch möglich, nur Warnungen zu berücksichtigen, die vom Bot vergeben wurden.
        """
        pass

    @automod_warn.command(name="add")
    async def automod_warn_add(self, ctx: commands.Context):
        """
        Erstelle eine neue automatische Verwarnung basierend auf dem Modlog eines Mitglieds.

        Mehere Parameter können definiert werden, wie die Anzahl an Warnungen, die Zeitspanne, die Stufe der Warnung, die nur von Automod vergebenen Warnungen berücksichtigt oder die Warnstufe, die gezählt werden soll (z.B. nur 3 Stufe-1-Warnungen sollen den Automod triggern).
        """
        guild = ctx.guild
        msg = await ctx.send(_("Lade Konfigurationsmenü..."))
        await asyncio.sleep(1)
        embed = discord.Embed(title=_("Automatische Verwarnung erstellen"))
        embed.colour = await self.bot.get_embed_colour(ctx)
        try:
            while True:
                number_of_warns = await self._ask_for_value(
                    ctx,
                    msg,
                    embed,
                    _("Wie viele Warnungen sollten den Automod auslösen?"),
                    need="valid_int",
                )
                if number_of_warns > 1:
                    break
                else:
                    await ctx.send(_("Dies muss höher als 1 sein."))
            while True:
                warn_level = await self._ask_for_value(
                    ctx,
                    msg,
                    embed,
                    _("Welche Stufe soll die automatische Verwarnung haben?"),
                    need="valid_int",
                )
                if 1 <= warn_level <= 5:
                    break
                else:
                    await ctx.send(_("Die Stufe muss zwischen 1 und 5 liegen."))
            warn_reason = await self._ask_for_value(
                ctx, msg, embed, _("Was ist der Grund für die automatische Verwarnung?"), optional=True
            )
            time: timedelta = await self._ask_for_value(
                ctx,
                msg,
                embed,
                _(
                    "Wie lange soll dieser Automod aktiv sein?\n\n"
                    "Zum Beispiel kannst du es so einstellen, dass es auslöst, wenn ein Mitglied 3 Warnungen"
                    " __innerhalb eines Tages__ erhält\nDas Weglassen dieses Werts wird den Automod dazu führen, über den "
                    "gesamten Modlog des Mitglieds ohne Zeitlimit zu suchen.\n\n"
                    "Format is the same as temp mutes/bans: `30m` = 30 minutes, `2h` = 2 hours, "
                    "`4d` = 4 days..."
                ),
                need="time",
                optional=True,
            )
            duration = None
            if warn_level == 2 or warn_level == 5:
                duration: timedelta = await self._ask_for_value(
                    ctx,
                    msg,
                    embed,
                    _(
                        "Level 2 and 5 Verwarnungen können temporär sein (unmute oder unban "
                        "nach einer bestimmten Zeit). Wie lange soll das Mitglied bestraft bleiben?\n"
                        "Überspringe diesen Wert, um die Stummschaltung/Verbannung unbegrenzt zu machen.\n"
                        "Das Zeitformat ist dasselbe wie bei der vorherigen Frage."
                    ),
                    need="time",
                    optional=True,
                )
            while True:
                lock_level = await self._ask_for_value(
                    ctx,
                    msg,
                    embed,
                    _(
                        "Soll der Automod nur bei einer bestimmten Stufe ausgelöst werden? "
                        "(z.B. nur 3 Warnungen der Stufe 1 sollten auslösen)\n"
                        "Sende die Stufe oder `0` zum Deaktivieren."
                    ),
                    need="valid_int",
                )
                if 0 <= lock_level <= 5:
                    break
                else:
                    await ctx.send(_("Level muss zwischen 0 und 5 liegen."))
                    await asyncio.sleep(1)
            only_automod = await self._ask_for_value(
                ctx,
                msg,
                embed,
                _(
                    "Soll der Automod nur von anderen Automod-Warnungen ausgelöst werden?\n"
                    "Falls aktiviert, werden Warnungen, die von einem normalen Moderator "
                    "ausgestellt wurden, nicht zum Zähler hinzugefügt.\n\n"
                    "Tippe `yes` oder `no`."
                ),
                need="yes_or_no",
                optional=False,
            )
        except asyncio.TimeoutError:
            await ctx.send(_("Zeitüberschreitung."))
            return
        await msg.delete()
        embed = discord.Embed(title=_("Einstellungen der automatischen Verwarnung"))
        embed = self._format_embed_for_autowarn(
            embed,
            number_of_warns,
            warn_level,
            warn_reason,
            lock_level,
            only_automod,
            time,
            duration,
        )
        embed.add_field(name="\u200B", value=_("Ist dies korrekt?"), inline=False)
        message = await ctx.send(embed=embed)
        pred = ReactionPredicate.yes_or_no(message, ctx.author)
        menus.start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for("reaction_add", check=pred, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send(_("Zeitüberschreitung."))
            return
        if not pred.result:
            await ctx.send(_("Bitte starten Sie den Vorgang erneut."))
            return
        async with self.data.guild(guild).automod.warnings() as warnings:
            warnings.append(
                {
                    "number": number_of_warns,
                    "time": time.total_seconds() if time else None,
                    "level": lock_level,
                    "automod_only": only_automod,
                    "warn": {
                        "level": warn_level,
                        "reason": warn_reason,
                        "duration": duration.total_seconds() if duration else None,
                    },
                }
            )
        await ctx.send(_("Die neue automatische Verwarnung wurde erfolgreich gespeichert!"))

    @automod_warn.command(name="delete", aliases=["del", "remove"])
    async def automod_warn_delete(self, ctx: commands.Context, index: int):
        """
        Lösche eine automatische Verwarnung.

        Du kannst alle automatischen Verwarnungen mit dem `[p]automod warn list` Befehl anzeigen.
        """
        guild = ctx.guild
        if index < 0:
            await ctx.send(_("Ungültiger Index, muss positiv sein."))
            return
        async with self.data.guild(guild).automod.warnings() as warnings:
            try:
                autowarn = warnings[index]
            except IndexError:
                await ctx.send(_("Ungültiger Index, muss positiv sein."))
                return
            embed = discord.Embed(title=_("Es wurde folgende automatische Verwarnung gelöscht:"))
            duration = autowarn["warn"]["duration"]
            embed = self._format_embed_for_autowarn(
                embed,
                autowarn["number"],
                autowarn["warn"]["level"],
                autowarn["warn"]["reason"],
                autowarn["level"],
                autowarn["automod_only"],
                timedelta(seconds=autowarn["time"]) if autowarn["time"] else None,
                timedelta(seconds=duration) if duration else None,
            )
            embed.set_footer(text=_("Bestätige mit den Reaktionen unten."))
            msg = await ctx.send(embed=embed)
            menus.start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
            pred = ReactionPredicate.yes_or_no(msg, ctx.author)
            try:
                await self.bot.wait_for("reaction_add", check=pred, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send(_("Zeitüberschreitung."))
                return
            if not pred.result:
                await ctx.send(_("Die automatische Verwarnung wurde nicht gelöscht."))
                return
            warnings.pop(index)
        await ctx.send(_("Die automatische Verwarnung wurde erfolgreich gelöscht."))

    @automod_warn.command(name="list")
    async def automod_warn_list(self, ctx: commands.Context):
        """
        Liste alle automatischen Verwarnungen auf.
        """
        guild = ctx.guild
        autowarns = await self.data.guild(guild).automod.warnings()
        if not autowarns:
            await ctx.send(_("Keine automatischen Verwarnungen registriert."))
            return
        text = ""
        for index, data in enumerate(autowarns):
            text += _("{index}. Level {level} Verwarnung (braucht {number} Verwarnungen zum Auslösen)\n").format(
                index=index, level=data["warn"]["level"], number=data["number"]
            )
        text = list(pagify(text, page_length=1900))
        pages = []
        for i, page in enumerate(text):
            pages.append(
                _("Seite {i}/{total}\n\n").format(i=i + 1, total=len(text))
                + page
                + _("\n*Nutze `{prefix}automod warn show` um Details anzuzeigen.*").format(
                    prefix=ctx.clean_prefix
                )
            )
        await menus.menu(ctx, pages=pages, controls=menus.DEFAULT_CONTROLS)

    @automod_warn.command(name="show")
    async def automod_warn_show(self, ctx: commands.Context, index: int):
        """
        Zeigt den Inhalt einer automatischen Verwarnung an.

        Der Index wird vom `[p]automod warn list` Befehl angezeigt.
        """
        guild = ctx.guild
        if index < 0:
            await ctx.send(_("Ungültiger Index, muss positiv sein."))
            return
        async with self.data.guild(guild).automod.warnings() as warnings:
            try:
                autowarn = warnings[index]
            except IndexError:
                await ctx.send(_("Ungültiger Index, muss positiv sein."))
                return
        embed = discord.Embed(title=_("Einstellungen:{index}").format(index=index))
        duration = autowarn["warn"]["duration"]
        embed = self._format_embed_for_autowarn(
            embed,
            autowarn["number"],
            autowarn["warn"]["level"],
            autowarn["warn"]["reason"],
            autowarn["level"],
            autowarn["automod_only"],
            timedelta(seconds=autowarn["time"]) if autowarn["time"] else None,
            timedelta(seconds=duration) if duration else None,
        )
        await ctx.send(embed=embed)

    @automod.group(name="antispam")
    async def automod_antispam(self, ctx: commands.Context):
        """
WarnSystem's antispam configuration.

        Wenn du WarnSystem's Antispam aktivierst, wird es deine Textkanäle sauberer halten, indem es Mitglieder entfernt und warnt, die unerwünschte Inhalte senden.
        """
        pass

    @automod_antispam.command(name="enable")
    async def automod_antispam_enable(self, ctx: commands.Context, enable: bool = None):
        """
        Aktiviere oder deaktiviere WarnSystem's Antispam.
        """
        guild = ctx.guild
        if enable is None:
            status = await self.cache.get_automod_antispam(guild)
            if status:
                status = _("enabled")
                status_change = _("Deaktiviert")
                setting = _("False")
            else:
                status = _("disabled")
                status_change = _("Aktiviert")
                setting = _("True")
            await ctx.send(
                _(
                    "WarnSystem's Antispam Funktionalität wird deine Textkanäle sauberer machen, indem sie Mitglieder entfernt und warnt, die unerwünschte Inhalte senden.\n\n"
                    "Antispam ist aktuell auf **{status}**.\n"
                    "{status_change} it with `{prefix}automod antispam enable {setting}`."
                ).format(
                    prefix=ctx.clean_prefix,
                    status=status,
                    status_change=status_change,
                    setting=setting,
                )
            )
            return
        await self.data.guild(guild).automod.antispam.enabled.set(enable)
        await self.cache.update_automod_antispam(guild)
        text = _("Antispam system ist: {status}.").format(
            status=_("enabled") if enable else _("disabled")
        )
        if await self.data.guild(guild).automod.enabled() is False and enable is True:
            text += _(
                "\n:warning: Automod ist deaktiviert, "
                "Aktiviere es mit `{prefix}automod enable True`."
            ).format(prefix=ctx.clean_prefix)
        await ctx.send(text)

    @automod_antispam.command(name="threshold")
    async def automod_antispam_threshold(
        self, ctx: commands.Context, max_messages: int, delay: int
    ):
        """
        Defines the spam threshold.

        Delay is in seconds.
        Example: `[p]automod antispam threshold 5 10` = maximum of 5 messages within 10 seconds\
before triggering the antispam.
        """
        guild = ctx.guild
        await self.data.guild(guild).automod.antispam.max_messages.set(max_messages)
        await self.data.guild(guild).automod.antispam.delay.set(delay)
        await self.cache.update_automod_antispam(guild)
        await ctx.send(
            _(
                "Done. A member will be considered as spamming if they sends "
                "more than {max_messages} within {delay} seconds."
            ).format(max_messages=max_messages, delay=delay)
        )

    @automod_antispam.command(name="delay")
    async def automod_antispam_delay(self, ctx: commands.Context, delay: int):
        """
        If antispam is triggered twice within this delay, perform the warn.

        Delay in seconds.
        If the antispam is triggered once, a simple warning is send in the chat, mentioning the\
member. If the same member triggers the antispam system a second time within this delay, there\
will be an actual warning taken, the one you define with `[p]automod antispam warn`.

        This is a way to tell the member they are close to being sanctioned. Of course you can\
disable this and immediately take actions by setting a delay of 0. Default is 60 seconds.
        """
        guild = ctx.guild
        await self.data.guild(guild).automod.antispam.delay_before_action.set(delay)
        await self.cache.update_automod_antispam(guild)
        if delay:
            await ctx.send(
                _(
                    "Done. If the antispam is triggered twice within {time} seconds, "
                    "actions will be taken. Use `{prefix}automod antispam warn` to "
                    "define the warn taken."
                ).format(time=delay, prefix=ctx.clean_prefix)
            )
        else:
            await ctx.send(
                _(
                    "Done. When triggered, the antispam will immediately perform the "
                    "warn you defined with `{prefix}automod antispam warn`."
                ).format(prefix=ctx.clean_prefix)
            )

    @automod_antispam.command(name="warn")
    async def automod_antispam_warn(
        self,
        ctx: commands.Context,
        level: int,
        duration: Optional[TimedeltaConverter],
        *,
        reason: str,
    ):
        """
        Define the warn taken when the antispam is triggered.

        The arguments for this command works the same way as the warn command.
        Examples: `[p]automod antispam warn 1 Spamming` `[p]automod antispam warn 2 30m Spamming`

        You can use the `[p]automod warn` command to configure an automatic warning after multiple\
automod infractions, like a mute after 3 warns.
        """
        guild = ctx.guild
        await self.data.guild(guild).automod.antispam.warn.set(
            {
                "level": level,
                "reason": reason,
                "time": duration.total_seconds() if duration else None,
            }
        )
        await self.cache.update_automod_antispam(guild)
        await ctx.send(
            _(
                "If the antispam is triggered by a member, they will now receive a level "
                "{level} warn {duration}for the following reason:\n{reason}"
            ).format(
                level=level,
                reason=reason,
                duration=_("that will last for {time} ").format(
                    time=self.api._format_timedelta(duration)
                )
                if duration
                else "",
            )
        )

    @automod_antispam.group(name="whitelist")
    async def automod_antispam_whitelist(self, ctx: commands.Context):
        """
        Manage word whitelist ignored for antispam.
        """
        pass

    @automod_antispam_whitelist.command(name="add")
    async def automod_antispam_whitelist_add(self, ctx: commands.Context, *words: str):
        """
        Add multiple words for the whitelist.

        If you want to add words with spaces, use quotes.
        """
        guild = ctx.guild
        if not words:
            await ctx.send_help()
            return
        async with self.data.guild(guild).automod.antispam.whitelist() as whitelist:
            for word in words:
                if word in whitelist:
                    await ctx.send(_("`{word}` is already in the whitelist.").format(word=word))
                    return
            whitelist.extend(words)
        await self.cache.update_automod_antispam()
        if len(words) == 1:
            await ctx.send(_("Added one word to the whitelist."))
        else:
            await ctx.send(_("Added {num} words to the whitelist.").format(num=len(words)))

    @automod_antispam_whitelist.command(name="delete", aliases=["del", "remove"])
    async def automod_antispam_whitelist_delete(self, ctx: commands.Context, *words: str):
        """
        Remove multiple words for the whitelist.

        If you want to remove words with spaces, use quotes.
        """
        guild = ctx.guild
        if not words:
            await ctx.send_help()
            return
        async with self.data.guild(guild).automod.antispam.whitelist() as whitelist:
            for word in words:
                if word not in whitelist:
                    await ctx.send(_("`{word}` isn't in the whitelist.").format(word=word))
                    return
            whitelist = [x for x in whitelist if x not in words]
        await self.cache.update_automod_antispam()
        if len(words) == 1:
            await ctx.send(_("Removed one word from the whitelist."))
        else:
            await ctx.send(_("Removed {num} words from the whitelist.").format(num=len(words)))

    @automod_antispam_whitelist.command(name="list")
    async def automod_antispam_whitelist_list(self, ctx: commands.Context):
        """
        List words in the whitelist.
        """
        guild = ctx.guild
        async with self.data.guild(guild).automod.antispam.whitelist() as whitelist:
            if not whitelist:
                await ctx.send(_("Whitelist is empty."))
                return
            text = _("__{num} words registered in the whitelist__\n").format(
                num=len(whitelist)
            ) + ", ".join(whitelist)
        for page in pagify(text, delims=[", ", "\n"]):
            await ctx.send(page)

    @automod_antispam_whitelist.command(name="clear")
    async def automod_antispam_whitelist_clear(self, ctx: commands.Context):
        """
        Clear the whitelist.
        """
        guild = ctx.guild
        await self.data.guild(guild).automod.antispam.whitelist.set([])
        await self.cache.update_automod_antispam()
        await ctx.tick()

    @automod_antispam.command(name="info")
    async def automod_antispam_info(self, ctx: commands.Context):
        """
        Show infos about the antispam system.
        """
        guild = ctx.guild
        automod_enabled = self.cache.is_automod_enabled(guild)
        antispam_settings = await self.data.guild(guild).automod.antispam.all()
        embed = discord.Embed(title=_("Antispam system settings"))
        description = ""
        if antispam_settings["enabled"] is True:
            description += _(":white_check_mark: Antispam system: **Enabled**\n")
        else:
            description += _(":x: Antispam system: **Disabled**\n")
        if automod_enabled:
            description += _(":white_check_mark: WarnSystem automod: **Enabled**\n")
        else:
            description += _(
                ":x: WarnSystem automod: **Disabled**\n"
                ":warning: The antispam won't work if the automod is disabled."
            )
        embed.description = description
        embed.add_field(
            name=_("Settings"),
            value=_(
                "Max messages allowed within the threshold: **{max_messages}**\n"
                "Threshold: **{delay} seconds**\n"
                "Delay before reset: **{reset_delay} seconds**  "
                "*(see `{prefix}automod antispam delay` for details about this)*\n"
                "Number of whitelisted words: {whitelist}"
            ).format(
                max_messages=antispam_settings["max_messages"],
                delay=antispam_settings["delay"],
                reset_delay=antispam_settings["delay_before_action"],
                prefix=ctx.clean_prefix,
                whitelist=len(antispam_settings["whitelist"]),
            ),
            inline=False,
        )
        level = antispam_settings["warn"]["level"]
        reason = antispam_settings["warn"]["reason"]
        if level == 2 or level == 5:
            time = _("Time: {time}\n").format(
                time=self.api._format_timedelta(
                    timedelta(seconds=antispam_settings["warn"]["time"])
                )
                if antispam_settings["warn"]["time"]
                else _("Unlimited.")
            )
        else:
            time = ""
        embed.add_field(
            name=_("Warning"),
            value=_(
                "This is the warning members will get when they break the antispam:\n\n"
                "Level: {level}\n"
                "{time}"
                "Reason: {reason}"
            ).format(level=level, reason=reason, time=time),
        )
        embed.color = await self.bot.get_embed_color(ctx)
        await ctx.send(embed=embed)
