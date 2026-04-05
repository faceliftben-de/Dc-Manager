"""
Custom error handling used for the cog and the API.

If you need to prevent and exception, do it like this:

.. code-block:: python

    warnsystem = bot.get_cog('WarnSystem')
    api = cog.api
    errors = cog.errors

    try:
        await api.warn(5, user, "my random reason")
    except discord.errors.Forbidden:
        print("Missing permissions")
    except errors.InvalidLevel:
        print("Wrong warning level")
    except:
        # occurs for any exception
        print("Fatal error")
    else:
        # executed if the try succeeded
        print("All good")
    finally:
        # always executed
        print("End of function")
"""

__all__ = [
    "InvalidLevel",
    "NotFound",
    "MissingMuteRole",
    "BadArgument",
    "MissingPermissions",
    "MemberTooHigh",
    "NotAllowedByHierarchy",
    "LostPermissions",
    "SuicidePrevention",
]


class InvalidLevel(Exception):
    """
   Das Level Argument für :func:`~warnsystem.api.warn` ist falsch.
    Es muss zwischen 1 und 5 liegen.
    """

    pass


class NotFound(Exception):
    """
    Etwas wurde nicht im WarnSystem-Daten gefunden. Der Sinn dieser Exception
    hängt davon ab, was Sie aufgerufen haben, es könnte ein fehlender WarnSystem-Kanal sein.
    """

    pass


class UserNotFound(Exception):
    """
    Ich konnte den Benutzer nicht finden. Das passiert, wenn du einen Benutzer erwähnst, der nicht mehr auf dem Server ist, oder wenn du eine ungültige ID oder einen ungültigen Namen angibst.
    """

    pass


class MissingMuteRole(Exception):
    """
    Du wolltest eine Stummschaltung vergeben, aber die Stummschaltungsrolle existiert nicht. Rufe
    :func:`~warnsystem.api.API.maybe_create_role` auf, um dies zu beheben.
    """

    pass


class BadArgument(Exception):
    """
    Die für Ihre Anfrage bereitgestellten Argumente sind falsch, überprüfen Sie die Typen.
    """

    pass


class MissingPermissions(Exception):
    """
    Der Bot verfügt nicht über die erforderliche Berechtigung, um eine Aktion durchzuführen.

    Diese Exception wird statt :class:`discord.errors.Forbidden` ausgelöst, um einen sinnlosen
    API-Aufruf zu vermeiden. Wir prüfen die Berechtigungen des Bots, bevor wir den Aufruf durchführen.
    """

    pass


class MemberTooHigh(Exception):
    """
    Der Mitglied ist über dem Bot in der Rollenhierarchie des Gilden.

    Um dies zu beheben, setze die höchste Rolle des Bots **über** die höchste Rolle des Mitglieds.
    ür mehr Informationen über Discord-Berechtigungen, lies das hier:\
    `<https://support.discordapp.com/hc/de/articles/206029707>`_

    is raised instead of :class:`discord.errors.Forbidden` to prevent a useless
    API call, we check the bot's permissions before calling.
    """

    pass


class NotAllowedByHierarchy(Exception):
    """
    Der Bot respektiert die Rollenhierarchie; Der Moderator, der die Verwarnung erteilt, muss eine Rolle haben, die höher als die verwarnte Person ist, damit die Verwarnung durchgeführt werden kann. 

    Der Moderator **muss** eine Rolle haben, die höher als die verwarnte Person ist, um fortzufahren.

    .. note:: This cannot be raised if the admins disabled the role hierarchy check.
    """

    pass


class LostPermissions(Exception):
    """
    Der Bot hat eine Berechtigung verloren.

    Dies kann die Berechtigung sein, Nachrichten in Kanal zu senden oder die Stummschaltungsrolle zu verwenden.
    """

    pass


class SuicidePrevention(Exception):
    """
    This is raised when the bot attempts to warn itself.

    Warning Red will cause issues and is not designed for this.
    """

    pass
