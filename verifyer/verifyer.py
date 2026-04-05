from redbot.core import commands, Config
import discord
from typing import Optional
from redbot.core.i18n import Translator, cog_i18n
from asyncio import sleep as asleep


_ = Translator("Verifyer", __file__)


@cog_i18n(_)
class Verifyer(commands.Cog):
    __version__ = "2.1.1"

    def format_help_for_context(self, ctx: commands.Context) -> str:
        # Thanks Sinbad! And Trusty in whose cogs I found this.
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nVersion: {self.__version__}"

    async def red_delete_data_for_user(self, *, requester, user_id):
        # This cog stores no EUD
        return

    def __init__(self):
        self.config = Config.get_conf(self, identifier=250620201622, force_registration=True)
        default_guild = {
            "text": "Willkommen auf [guild]! Bitte verwende ``[p]verify`` um Zugang zum Rest des Servers zu erhalten.",
            "verifiedtext": "",
            "role": None,
            "memrole": None,
            "enabled": False,
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if await self.config.guild(member.guild).enabled():
            text = await self.config.guild(member.guild).text()
            if text:
                await member.send(text)
            role = await self.config.guild(member.guild).role()
            if role:
                await member.add_roles(
                    member.guild.get_role(role), reason=_("Verifizierung erforderlich.")
                )

    @commands.guild_only()
    @commands.command()
    async def verify(self, ctx, member: Optional[discord.Member]):
        if not member:
            member = ctx.author
        try:
            verifiedtext = await self.config.guild(ctx.guild).verifiedtext()
            if verifiedtext:
                await member.send(verifiedtext)
        except discord.Forbidden:
            pass
        role = await self.config.guild(ctx.guild).role()
        if role:
            try:
                await member.remove_roles(
                    ctx.guild.get_role(role), reason=_("Mitglied hat sich verifiziert.")
                )
            except:
                pass
        memrole = await self.config.guild(ctx.guild).memrole()
        if memrole:
            try:
                await member.add_roles(
                    ctx.guild.get_role(memrole), reason=_("Mitglied hat sich verifiziert.")
                )
            except discord.Forbidden:
                await ctx.send(
                    _(
                        "Oh, da ist ist ein Fehler aufgetreten.\nBitte kontaktiere einen Server-Administrator und bitte ihn, sicherzustellen, dass ich die richtigen Berechtigungen habe."
                    )
                )
        try:
            await ctx.tick()
            await asleep(5)
            await ctx.message.remove()
        except:
            pass

    @commands.guild_only()
    @commands.group()
    @commands.admin()
    async def verifyerset(self, ctx):
        """Einstellungen für Verifyer"""
        pass

    @commands.guild_only()
    @verifyerset.command()
    @commands.bot_has_permissions(manage_roles=True)
    async def enable(self, ctx):
        """Aktiviere Verifyer.\nDies ist pro Server."""
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(_("Verifyer aktiviert."))

    @commands.guild_only()
    @verifyerset.command()
    async def disable(self, ctx):
        """Deaktiviere Verifyer.\nDies ist pro Server."""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send(_("Verifyer deaktiviert."))

    @commands.guild_only()
    @verifyerset.command()
    async def role(self, ctx, role: Optional[discord.Role]):
        """Setze die Rolle, die einem Benutzer beim Beitritt zum Server zugewiesen wird.\n\nLasse es leer, um diese Funktion zu deaktivieren."""
        if not role:
            await self.config.guild(ctx.guild).role.set(None)
            await ctx.send_help()
            await ctx.send(_("Verifikationsrolle deaktiviert."))
        else:
            await self.config.guild(ctx.guild).role.set(role.id)
            await ctx.send(
                _(
                    "Verifikationsrolle auf {rolemention} gesetzt.\nBitte stelle sicher, dass meine Rolle höher ist als {rolemention} in der Discord-Rollenhierarchie."
                ).format(rolemention=role.mention)
            )

    @commands.guild_only()
    @verifyerset.command()
    async def message(self, ctx, *, text: Optional[str]):
        """Sende eine Nachricht an einen Benutzer, wenn er dem Server beitritt.\n\nLasse es leer, um diese Funktion zu deaktivieren."""
        await self.config.guild(ctx.guild).text.set(text)
        if text:
            await ctx.send(_("Nachricht gesetzt zu: ```{text}```").format(text=text))
        else:
            await ctx.send(_("DM bei Beitritt deaktiviert."))

    @commands.guild_only()
    @verifyerset.command()
    async def verifiedmessage(self, ctx, *, text: Optional[str]):
        """Sende eine Nachricht an einen Benutzer, wenn er sich verifiziert.\n\nLasse es leer, um diese Funktion zu deaktivieren."""
        await self.config.guild(ctx.guild).verifiedtext.set(text)
        if text:
            await ctx.send(_("Nachricht gesetzt zu: ```{text}```").format(text=text))
        else:
            await ctx.send(_("Nachricht bei Verifikation deaktiviert."))

    @commands.guild_only()
    @verifyerset.command()
    async def memberrole(self, ctx, role: Optional[discord.Role]):
        """Setze die Rolle, die einem Benutzer zugewiesen wird, wenn er dem Server beitritt.\n\nLasse es leer, um diese Funktion zu deaktivieren."""
        if not role:
            await self.config.guild(ctx.guild).role.set(None)
            await ctx.send_help()
            await ctx.send(_("Mitgliederrolle deaktiviert."))
        else:
            await self.config.guild(ctx.guild).memrole.set(role.id)
            await ctx.send(_("Mitgliederrolle auf {rolemention} gesetzt.").format(rolemention=role.mention))
