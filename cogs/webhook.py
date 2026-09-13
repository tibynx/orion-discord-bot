"""Cog for managing and interacting with Discord webhooks."""
from typing import Union
import discord
from discord.ext import commands
from discord import app_commands
import filetype
from config import SUCCESS_EMOJI, ERROR_EMOJI, PREVIOUS_EMOJI, NEXT_EMOJI


# Modal for sending messages via webhook ID
class WebhookSendModal(discord.ui.Modal):
    """Modal for sending a message using a specific webhook."""
    def __init__(self, bot, webhook: discord.Webhook):
        """Initialize the modal with the webhook instance."""
        super().__init__(title=f"Send Message via {webhook.name}")
        self.bot = bot
        self.webhook = webhook

    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.long,
        placeholder="Enter the message to send. Markdown formatting is supported. (no preview)",
        required=True,
        max_length=2000,
    )
    add_files = discord.ui.Label(
        text="Upload Attachments",
        component=discord.ui.FileUpload(
            max_values=10,
            required=False
        )
    )
    allowed_mentions_toggles = discord.ui.Label(
        text="Allowed Mentions",
        description="Whether to ping mentions in the message.",
        component=discord.ui.CheckboxGroup(
            options=[
                discord.CheckboxGroupOption(label="Members", default=True),
                discord.CheckboxGroupOption(label="Roles", default=True),
                discord.CheckboxGroupOption(label="@everyone and @here", default=False)
            ],
            required=False
        )
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Send the message through the webhook upon submission."""
        await interaction.response.defer(ephemeral=True)
        uploaded_files = self.add_files.component.values or []
        files = [await attachment.to_file() for attachment in uploaded_files]
        selected = self.allowed_mentions_toggles.component.values
        mention_user = "Members" in selected
        mention_role = "Roles" in selected
        mention_everyone = "@everyone and @here" in selected
        allowed_mentions = discord.AllowedMentions(
            users=mention_user,
            roles=mention_role,
            everyone=mention_everyone,
        )
        await self.webhook.send(
            content=self.message.value,
            files=files,
            allowed_mentions=allowed_mentions
        )
        await interaction.followup.send(
            f"{SUCCESS_EMOJI} Message sent successfully.",
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle errors during webhook message submission."""
        if isinstance(error, discord.NotFound):
            msg = f"{ERROR_EMOJI} The specified webhook cannot be found."
        elif isinstance(error, discord.Forbidden):
            msg = f"{ERROR_EMOJI} I don't have permission to send messages with this webhook."
        elif isinstance(error, ValueError):
            msg = f"{ERROR_EMOJI} {error}"
        else:
            self.bot.logger.error(
                "Unhandled error in WebhookSendModal.on_submit: %r",
                error,
                exc_info=(type(error), error, error.__traceback__),
            )
            msg = f"{ERROR_EMOJI} An unexpected error occurred."

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


# Webhook deletion dialog
class WebhookDeleteDialog(discord.ui.LayoutView):
    """View for confirming webhook deletion."""
    def __init__(self, webhook: discord.Webhook):
        """Initialize the dialog with the target webhook."""
        super().__init__(timeout=30)
        self.webhook = webhook
        self.message = None

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## Delete {webhook.name}\n"
                f"Are you sure you want to delete the **{webhook.name}** webhook? "
                "This action cannot be undone."
            )
        )
        # Cancel button
        cancel_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary, label="Cancel"
        )
        # Delete button
        delete_button = discord.ui.Button(
            style=discord.ButtonStyle.danger, label="Delete"
        )
        cancel_button.callback = self.cancel_button_callback
        delete_button.callback = self.delete_button_callback
        self.cancel_button = cancel_button
        self.delete_button = delete_button
        buttons = discord.ui.ActionRow(cancel_button, delete_button) # Add buttons to the row
        container.add_item(buttons)
        self.add_item(container)

    # If we cancel, the message just gets removed
    async def cancel_button_callback(self, interaction: discord.Interaction) -> None:
        """Cancel the deletion process and remove the dialog."""
        await interaction.response.defer()
        await interaction.delete_original_response()

    # If we delete, it deletes the message, then tries to delete the webhook
    async def delete_button_callback(self, interaction: discord.Interaction) -> None:
        """Execute the webhook deletion."""
        await interaction.response.defer()
        try:
            await self.webhook.delete()
            await interaction.delete_original_response()
            await interaction.followup.send(
                f"{SUCCESS_EMOJI} Deleted **{self.webhook.name}** webhook successfully.",
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.delete_original_response()
            await interaction.followup.send(
                f"{ERROR_EMOJI} The specified webhook cannot be found.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.delete_original_response()
            await interaction.followup.send(
                f"{ERROR_EMOJI} I don't have permission to delete this webhook.",
                ephemeral=True
            )

    async def on_timeout(self) -> None:
        """Disable buttons when the view times out."""
        self.cancel_button.disabled = True
        self.delete_button.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
        self.stop()


# Webhook buttons
class WebhookButtons(discord.ui.View):
    """View providing management buttons for a webhook."""
    def __init__(self, webhook: discord.Webhook):
        """Initialize the buttons with the webhook instance."""
        super().__init__(timeout=180)
        self.webhook = webhook
        self.message = None

    # Send message button
    # Sends the webhook message modal
    @discord.ui.button(label="Send Message", style=discord.ButtonStyle.primary)
    async def send_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Display the modal to send a message via this webhook."""
        # Prevent sending messages to forum channels
        if isinstance(self.webhook.channel, discord.ForumChannel):
            await interaction.response.send_message(
                f"{ERROR_EMOJI} You cannot send messages to forum webhooks.",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(WebhookSendModal(interaction.client, self.webhook))

    # Show webhook URL button
    # Sends the webhook URL in an ephemeral message
    @discord.ui.button(label="Show Webhook URL", style=discord.ButtonStyle.secondary)
    async def show_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Display the webhook's URL securely."""
        await interaction.response.send_message(
            f"**{discord.utils.escape_markdown(self.webhook.name)}** Webhook URL:\n```{self.webhook.url}```", ephemeral=True
        )

    # Delete webhook button
    # Sends the webhook deletion confirmation modal
    @discord.ui.button(label="Delete Webhook", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Display the deletion confirmation dialog."""
        dialog = WebhookDeleteDialog(self.webhook)
        await interaction.response.send_message(view=dialog, ephemeral=True)
        dialog.message = await interaction.original_response()

    async def on_timeout(self) -> None:
        """Disable buttons when the view times out."""
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
        self.stop()


# Separate delete button for channel follower and application webhooks
class WebhookDeleteButton(discord.ui.View):
    """View providing only a delete button for certain webhook types."""
    def __init__(self, webhook: discord.Webhook):
        """Initialize the button with the webhook instance."""
        super().__init__(timeout=180)
        self.webhook = webhook
        self.message = None

    # Delete webhook button
    # Sends the webhook deletion confirmation modal
    @discord.ui.button(label="Delete Webhook", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Display the deletion confirmation dialog."""
        dialog = WebhookDeleteDialog(self.webhook)
        await interaction.response.send_message(view=dialog, ephemeral=True)
        dialog.message = await interaction.original_response()

    async def on_timeout(self) -> None:
        """Disable buttons when the view times out."""
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
        self.stop()


# Pagination view for webhooks
class WebhookPaginationView(discord.ui.View):
    """View for paginating webhook list embeds."""
    def __init__(self, webhooks: list[discord.Webhook], guild_name: str):
        """Initialize the pagination view with webhooks and guild name."""
        super().__init__(timeout=180)
        self.webhooks = webhooks
        self.guild_name = guild_name
        self.message = None
        self.current_page = 0
        self.per_page = 5
        self.total_pages = (len(webhooks) - 1) // self.per_page + 1
        # Set pagination emojis from config
        self.prev_page.emoji = PREVIOUS_EMOJI
        self.next_page.emoji = NEXT_EMOJI
        self.update_buttons()

    def update_buttons(self) -> None:
        """Enable or disable pagination buttons based on current page."""
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.total_pages - 1

    def build_embed(self) -> discord.Embed:
        """Build the embed for the current page."""
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_webhooks = self.webhooks[start:end]

        embed = discord.Embed(
            title=f"Webhooks in {self.guild_name}",
            color=None
        )
        for webhook in page_webhooks:
            embed.add_field(
                name=webhook.name,
                value=(
                    f"Channel: {webhook.channel.mention}\n"
                    f"Created by: {webhook.user.mention}\nID: `{webhook.id}`"
                ),
                inline=False
            )
        embed.set_footer(
            text=f"Page {self.current_page + 1}/{self.total_pages}  •  Total: {len(self.webhooks)}"
        )
        return embed

    # Previous page button
    @discord.ui.button(style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the previous page of webhooks."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    # Next page button
    @discord.ui.button(style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Go to the next page of webhooks."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    async def on_timeout(self) -> None:
        """Disable buttons when the view times out."""
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
        self.stop()



# Webhook commands
class Webhook(commands.Cog):
    """Cog for advanced webhook management."""
    def __init__(self, bot):
        """Initialize the cog with the bot instance."""
        self.bot = bot

    # Helper to classify read-only webhooks
    @staticmethod
    def _is_readonly_webhook(webhook: discord.Webhook) -> bool:
        """Check if a webhook is read-only based on its type."""
        # Return True if a webhook type is a channel follower or application.
        return webhook.type in (
            discord.WebhookType.channel_follower, discord.WebhookType.application
        )

    # Helper to check if a webhook has a token
    @staticmethod
    def _has_token(webhook: discord.Webhook) -> bool:
        """Check if a webhook has a token associated with it."""
        return webhook.token is not None




    # Group for editing webhooks
    webhook_edit_group = app_commands.Group(
        name="webhookedit",
        description="Edit webhook details.",
        # Requires manage webhooks permission
        default_permissions=discord.Permissions(manage_webhooks=True),
        guild_only=True
    )



    # Get details about a webhook
    @app_commands.command(
        name="webhookget",
        description="Get details about a webhook."
    )
    @app_commands.guild_only()
    # Requires manage webhooks permission
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        webhook_id="The ID of the webhook to fetch"
    )
    async def webhook_get(self, interaction: discord.Interaction, webhook_id: str) -> None:
        """Fetch and display details of a specific webhook."""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            embed = discord.Embed(
                title=webhook.name,
                color=None,
                description=f"🕔 Created at <t:{int(webhook.created_at.timestamp())}:R> "
                            f"by {webhook.user.mention}"
            )
            embed.add_field(name="Channel", value=webhook.channel.mention, inline=True)
            embed.add_field(name="Type", value=webhook.type.name.title(), inline=True)
            embed.add_field(name="ID", value=f"`{webhook.id}`", inline=True)
            embed.set_thumbnail(url=webhook.display_avatar.url)
            # Check if the webhook user is a bot
            if webhook.user.bot:
                embed.set_footer(
                    text="🛈  This webhook is managed by "
                         f"{webhook.user.name}#{webhook.user.discriminator}."
                )
            # Check if it's an application or channel follower webhook, or lacks a token (we can only delete those)
            if self._is_readonly_webhook(webhook) or not self._has_token(webhook):
                view = WebhookDeleteButton(webhook)
                await interaction.response.send_message(
                    embed=embed, view=view, ephemeral=True
                )
                view.message = await interaction.original_response()
                return
            view = WebhookButtons(webhook)
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
            view.message = await interaction.original_response()
            return
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to get webhook details.",
                ephemeral=True
            )
        except discord.NotFound:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found.", ephemeral=True
            )


    # List all webhooks
    @app_commands.command(
        name="webhooklist",
        description="List all webhooks in the server. "
                    "Use the /webhookget command to get info about a specific webhook."
    )
    @app_commands.guild_only()
    # Requires manage webhooks permission
    @app_commands.default_permissions(manage_webhooks=True)
    async def webhook_list(self, interaction: discord.Interaction) -> None:
        """List all webhooks available in the current guild."""
        await interaction.response.defer(ephemeral=True)
        try:
            webhooks = await interaction.guild.webhooks()
            # Check if there are no webhooks
            if not webhooks:
                return await interaction.followup.send(
                    f"{ERROR_EMOJI} No webhooks found in this server.",
                    ephemeral=True
                )
            view = WebhookPaginationView(webhooks, interaction.guild.name)
            view.message = await interaction.followup.send(
                embed=view.build_embed(), view=view, ephemeral=True
            )
            return
        except discord.Forbidden:
            return await interaction.followup.send(
                f"{ERROR_EMOJI} I don't have permission to list webhooks.",
                ephemeral=True
            )


    # Create a webhook
    @app_commands.command(
        name="webhookcreate",
        description="Create a webhook. The webhook will be associated with this bot."
    )
    @app_commands.guild_only()
    # Requires manage webhooks permission
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        channel="The channel to create the webhook in",
        name="The name of the webhook"
    )
    async def webhook_create(
        self, interaction: discord.Interaction,
        channel: Union[
            discord.TextChannel, discord.ForumChannel,
            discord.StageChannel, discord.VoiceChannel
        ],
        name: str
    ) -> None:
        """Create a new webhook in a specified channel."""
        try:
            webhook = await channel.create_webhook(name=name)
            embed = discord.Embed(
                title=webhook.name,
                color=None,
                description=f"🕔 Created at <t:{int(webhook.created_at.timestamp())}:R> "
                            f"by {webhook.user.mention}"
            )
            embed.add_field(name="Channel", value=webhook.channel.mention, inline=True)
            embed.add_field(name="Type", value=webhook.type.name.title(), inline=True)
            embed.add_field(name="ID", value=f"`{webhook.id}`", inline=True)
            embed.set_thumbnail(url=webhook.display_avatar.url)
            # We don't check if the webhook user is a bot, because it always will be
            embed.set_footer(
                text="🛈  Use the /webhookedit commands to "
                     "edit this webhook's details."
            )
            view = WebhookButtons(webhook)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Created **{webhook.name}** webhook successfully.",
                embed=embed, view=view, ephemeral=True
            )
            view.message = await interaction.original_response()
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to create webhooks in this channel.",
                ephemeral=True
            )
        except discord.HTTPException as error:
            if error.code == 30007: # Max webhooks reached
                await interaction.response.send_message(
                    f"{ERROR_EMOJI} This channel has reached the maximum number of webhooks.",
                    ephemeral=True
                )
            else:
                raise error


    # Delete a webhook (sends confirmation modal)
    @app_commands.command(
        name="webhookdelete",
        description="Delete a webhook."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        webhook_id="The ID of the webhook to delete"
    )
    async def webhook_delete(self, interaction: discord.Interaction, webhook_id: str) -> None:
        """Display a confirmation dialog to delete a webhook."""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to delete webhooks.",
                ephemeral=True
            )
        except discord.NotFound:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found.",
                ephemeral=True
            )
        dialog = WebhookDeleteDialog(webhook)
        await interaction.response.send_message(view=dialog, ephemeral=True)
        dialog.message = await interaction.original_response()
        return None

    # Show webhook url
    @app_commands.command(
        name="webhookurl",
        description="Show the URL of a webhook."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        webhook_id="The ID of the webhook to show the URL for"
    )
    async def webhook_url(self, interaction: discord.Interaction, webhook_id: str) -> None:
        """Display the URL of a webhook."""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            if self._is_readonly_webhook(webhook) or not self._has_token(webhook):
                return await interaction.response.send_message(
                    f"{ERROR_EMOJI} You cannot get the URL for this webhook.",
                    ephemeral=True
                )
            await interaction.response.send_message(
                f"**{discord.utils.escape_markdown(webhook.name)}** Webhook URL:\n```{webhook.url}```", ephemeral=True
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to get webhook URLs.",
                ephemeral=True
            )
        except discord.NotFound:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found.",
                ephemeral=True
            )


    # Send a message through a webhook using its ID (opens modal)
    @app_commands.command(
        name="webhookmsg",
        description="Send a message through a webhook."
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.describe(
        webhook_id="The ID of the webhook to send the message through"
    )
    async def webhook_send(self, interaction: discord.Interaction, webhook_id: str) -> None:
        """Display a modal to send a message via a webhook."""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to use webhooks.",
                ephemeral=True
            )
        except discord.NotFound:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found.",
                ephemeral=True
            )
        # Prevent sending messages to forum channels
        if isinstance(webhook.channel, discord.ForumChannel):
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} You cannot send messages to forum webhooks.",
                ephemeral=True
            )
        # Check if it's a channel follower, application webhook, or lacks a token
        if self._is_readonly_webhook(webhook) or not self._has_token(webhook):
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} You cannot send messages with this webhook.",
                ephemeral=True
            )
        # Send the webhook message modal
        await interaction.response.send_modal(
            WebhookSendModal(self.bot, webhook)
        )


    # Change the name of a webhook
    @webhook_edit_group.command(
        name="name",
        description="Edit the name of a webhook."
    )
    @app_commands.describe(
        webhook_id="The ID of the webhook.",
        name="The new name of the webhook."
    )
    async def webhook_edit_name(
            self, interaction: discord.Interaction, webhook_id: str, name: str
    ) -> None:
        """Change the name of a specific webhook."""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            # Check if it's a channel follower or application webhook
            if self._is_readonly_webhook(webhook):
                return await interaction.response.send_message(
                    f"{ERROR_EMOJI} You cannot rename this webhook.",
                    ephemeral=True
                )
            old_name = webhook.name
            await webhook.edit(name=name)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Webhook **{old_name}** renamed "
                f"to **{webhook.name}** successfully.",
                ephemeral=True
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to edit webhooks.",
                ephemeral=True
            )
        except discord.NotFound:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found.",
                ephemeral=True
            )


    # Change the avatar of a webhook
    @webhook_edit_group.command(
        name="avatar",
        description="Edit the avatar of a webhook."
    )
    @app_commands.describe(
        webhook_id="The ID of the webhook.",
        avatar="The new avatar of the webhook."
    )
    async def webhook_edit_avatar(
            self, interaction: discord.Interaction, webhook_id: str, avatar: discord.Attachment
    ) -> None:
        """Change the avatar of a specific webhook."""
        await interaction.response.defer(ephemeral=True)
        avatar_bytes = await avatar.read() # Read the file content once
        kind = filetype.guess(avatar_bytes) # Validate MIME type using magic bytes
        if kind is None or kind.mime not in {'image/png', 'image/jpeg', 'image/gif'}:
            return await interaction.followup.send(
                f"{ERROR_EMOJI} Invalid file type. Only PNG, JPEG, and GIF images are supported.",
                ephemeral=True
            )
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            # Check if it's a channel follower or application webhook
            if self._is_readonly_webhook(webhook):
                return await interaction.followup.send(
                    f"{ERROR_EMOJI} You cannot change the avatar for this webhook.",
                    ephemeral=True
                )
            await webhook.edit(avatar=avatar_bytes)
            await interaction.followup.send(
                f"{SUCCESS_EMOJI} Webhook **{webhook.name}** avatar changed successfully.",
                ephemeral=True
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                f"{ERROR_EMOJI} I don't have permission to edit webhooks.",
                ephemeral=True
            )
        except discord.NotFound:
            return await interaction.followup.send(
                f"{ERROR_EMOJI} The specified webhook cannot be found.",
                ephemeral=True
            )


    # Change the channel of a webhook
    @webhook_edit_group.command(
        name="channel",
        description="Edit the channel of a webhook."
    )
    @app_commands.describe(
        webhook_id="The ID of the webhook.",
        channel="The new channel of the webhook."
    )
    async def webhook_edit_channel(
        self, interaction: discord.Interaction, webhook_id: str,
        channel: Union[
            discord.TextChannel, discord.ForumChannel,
            discord.StageChannel, discord.VoiceChannel
        ]
    ) -> None:
        """Move a webhook to a different channel."""
        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
            # Check if it's a channel follower or application webhook
            if self._is_readonly_webhook(webhook):
                return await interaction.response.send_message(
                    f"{ERROR_EMOJI} You cannot change the channel for this webhook.",
                    ephemeral=True
                )
            await webhook.edit(channel=channel)
            await interaction.response.send_message(
                f"{SUCCESS_EMOJI} Webhook **{webhook.name}** channel updated successfully.",
                ephemeral=True
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} I don't have permission to edit webhooks.",
                ephemeral=True
            )
        except discord.NotFound:
            return await interaction.response.send_message(
                f"{ERROR_EMOJI} The specified webhook cannot be found.",
                ephemeral=True
            )



async def setup(bot):
    """Add the Webhook cog to the bot."""
    await bot.add_cog(Webhook(bot))
