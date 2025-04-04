import discord
import asyncio
import random
import string
import requests
import json
import os
from datetime import datetime, timedelta
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Import configuration
from dotenv import load_dotenv
from config import *

# Load environment variables
load_dotenv()
TOKEN = os.environ.get('DISCORD_TOKEN')  # Get token from environment variable

# Load messages from JSON file
def load_messages():
    try:
        with open('messages.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading messages: {e}")
        return {}

# Global messages dictionary
MESSAGES = load_messages()

# Intents configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot initialization
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Dictionary to store active verifications
# Structure: {user_id: {'habbo_user': str, 'code': str, 'expires_at': datetime, 'task': asyncio.Task}}
active_verifications = {}

@bot.event
async def on_ready():
    # Check if bot.user exists before accessing name attribute
    if bot.user:
        print(MESSAGES.get('bot', {}).get('online', '{bot_name} is online!').format(bot_name=bot.user.name))
    else:
        print('Bot is online but user object is not available')
    # Check if bot.user exists before accessing id attribute
    if bot.user:
        print(MESSAGES.get('bot', {}).get('id', 'ID: {bot_id}').format(bot_id=bot.user.id))
    else:
        print('Bot ID not available')
    print('------')

# Function to generate random code
def generate_code():
    characters = string.ascii_uppercase + string.digits
    code = ''.join(random.choice(characters) for _ in range(6))
    return f"{CODE_PREFIX}{code}"

# Function to verify Habbo user
async def verify_user(user_id, habbo_user, code):
    try:
        url = f"https://www.{SERVER_OPTION}/api/public/users?name={habbo_user}"
        response = requests.get(url)
        data = response.json()
        
        # Check if user exists or has open profile
        if 'error' in data or not data:
            return "user_not_found"
        
        # Get exact username from API
        exact_name = data.get('name', habbo_user)
        
        if 'motto' in data and data['motto'] == code:
            return {'verified': True, 'exact_name': exact_name}
        return {'verified': False, 'exact_name': exact_name}
    except Exception as e:
        print(f"Error verifying user: {e}")
        return {'verified': False, 'exact_name': habbo_user}

# Function to create custom image
async def create_verification_image(habbo_user):
    try:
        # Download Habbo avatar
        avatar_url = f"http://www.{SERVER_OPTION}/habbo-imaging/avatarimage?&user={habbo_user}&action=std&direction=2&head_direction=3&img_format=png&gesture=sml&headonly=0&size=l"
        response = requests.get(avatar_url)
        avatar_img = Image.open(BytesIO(response.content))
        
        # Create base image
        img_width, img_height = 500, 200
        
        # Check if custom background image exists
        if BACKGROUND_IMAGE and os.path.exists(BACKGROUND_IMAGE):
            try:
                # Load background image
                background = Image.open(BACKGROUND_IMAGE).convert('RGBA')
                # Resize to correct size
                background = background.resize((img_width, img_height))
                img = background
            except Exception as e:
                print(f"Error loading background image: {e}")
                # Fallback to solid color
                img = Image.new('RGBA', (img_width, img_height), BACKGROUND_COLOR)
        else:
            # Use solid color as background
            img = Image.new('RGBA', (img_width, img_height), BACKGROUND_COLOR)
        
        draw = ImageDraw.Draw(img)
        
        img.paste(avatar_img, (20, 0), avatar_img)
        
        # Load custom font or use fallback
        try:
            if CUSTOM_FONT and os.path.exists(CUSTOM_FONT):
                font = ImageFont.truetype(CUSTOM_FONT, FONT_SIZE)
            else:
                # Fallback to system fonts
                try:
                    font = ImageFont.truetype("arialbd.ttf", FONT_SIZE)  # Arial Bold
                except IOError:
                    try:
                        font = ImageFont.truetype("arial.ttf", FONT_SIZE)  # Arial
                    except IOError:
                        font = ImageFont.load_default()
        except Exception as e:
            print(f"Error loading font: {e}")
            font = ImageFont.load_default()
        
        # Add custom text
        draw.text((200, 60), f"{habbo_user},", font=font, fill=MAIN_TEXT_COLOR)
        draw.text((200, 90), VERIFICATION_TEXT, font=font, fill=SECONDARY_TEXT_COLOR)
        
        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, 'PNG')
        buffer.seek(0)
        
        return buffer
    except Exception as e:
        print(f"Error creating image: {e}")
        return None

# Function for continuous verification process
async def verification_process(ctx, user_id, habbo_user, code):
    expires_at = datetime.now() + timedelta(seconds=EXPIRATION_TIME)
    
    # Store instruction message to edit it later
    status_message = active_verifications[user_id].get('message')
    
    while datetime.now() < expires_at:
        if user_id not in active_verifications:
            # Verification was cancelled
            return
            
        result = await verify_user(user_id, habbo_user, code)
        
        if result == "user_not_found":
            # Get message from messages.json or use default
            user_not_found_msg = MESSAGES.get('verification_process', {}).get('user_not_found', "{mention} Could not find user **{habbo_user}** on Habbo. Please check if the name is correct or if the profile is open for public viewing.")
            formatted_msg = user_not_found_msg.format(
                mention=ctx.author.mention,
                habbo_user=habbo_user
            )
            
            # Edit existing message instead of sending a new one
            if status_message:
                await status_message.edit(content=formatted_msg)
            else:
                status_message = await ctx.send(formatted_msg)
            
            if user_id in active_verifications:
                del active_verifications[user_id]
            return
            
        if result['verified']:
            # Use exact name returned by API
            exact_name = result['exact_name']
            # User verified successfully
            try:
                # Get role
                guild = ctx.guild
                role = discord.utils.get(guild.roles, name=VERIFIED_ROLE)
                
                # Create role if it doesn't exist
                if role is None:
                    role = await guild.create_role(name=VERIFIED_ROLE, colour=discord.Colour.green())
                
                # Check bot permissions
                bot_member = ctx.guild.me
                if not bot_member.guild_permissions.manage_roles:
                    # Get message from messages.json or use default
                    no_permission_msg = MESSAGES.get('verification_process', {}).get('bot_no_permission', "{mention} Error: Bot doesn't have permission to manage roles. Please ask an administrator to give the 'Manage Roles' permission to the bot.")
                    formatted_msg = no_permission_msg.format(
                        mention=ctx.author.mention
                    )
                    
                    if status_message:
                        await status_message.edit(content=formatted_msg)
                    else:
                        await ctx.send(formatted_msg)
                    return

                # Check role hierarchy
                if role.position >= bot_member.top_role.position:
                    # Get message from messages.json or use default
                    role_hierarchy_msg = MESSAGES.get('verification_process', {}).get('role_hierarchy_error', "{mention} Error: The '{role_name}' role is above the bot's highest role. Please ask an administrator to move the bot's role above the '{role_name}' role.")
                    formatted_msg = role_hierarchy_msg.format(
                        mention=ctx.author.mention,
                        role_name=VERIFIED_ROLE
                    )
                    
                    if status_message:
                        await status_message.edit(content=formatted_msg)
                    else:
                        await ctx.send(formatted_msg)
                    return

                # Assign role
                member = ctx.author
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    # Get message from messages.json or use default
                    role_assign_error_msg = MESSAGES.get('verification_process', {}).get('role_assign_error', "{mention} Error: Could not assign role. Please check if the bot has the necessary permissions and if the bot's role is above the '{role_name}' role.")
                    formatted_msg = role_assign_error_msg.format(
                        mention=ctx.author.mention,
                        role_name=VERIFIED_ROLE
                    )
                    
                    if status_message:
                        await status_message.edit(content=formatted_msg)
                    else:
                        await ctx.send(formatted_msg)
                    return
                
                # Create custom image
                image = await create_verification_image(exact_name)
                
                # Change user's nickname if setting is enabled
                if CHANGE_NICKNAME:
                    # Change user's nickname to verified Habbo name
                    await member.edit(nick=exact_name)
                    
                    # Get message from messages.json or use default
                    success_nickname_msg = MESSAGES.get('verification_process', {}).get('success_with_nickname', "{mention} Verification completed successfully! Your nickname has been changed to **{habbo_user}**.") 
                    formatted_msg = success_nickname_msg.format(
                        mention=ctx.author.mention,
                        habbo_user=exact_name
                    )
                    
                    # Inform that nickname was changed
                    if status_message:
                        if image:
                            # To send a file with the edit, we need to delete the old message and send a new one
                            await status_message.delete()
                            status_message = await ctx.send(formatted_msg, file=discord.File(fp=image, filename="verified.png"))
                        else:
                            await status_message.edit(content=formatted_msg) 
                    else:
                        if image:
                            status_message = await ctx.send(formatted_msg, file=discord.File(fp=image, filename="verified.png"))
                        else:
                            status_message = await ctx.send(formatted_msg)
                else:
                    # If not changing nickname, send success message with image
                    # Get message from messages.json or use default
                    success_msg = MESSAGES.get('verification_process', {}).get('success', "{mention} Verification completed successfully!")
                    formatted_msg = success_msg.format(
                        mention=ctx.author.mention
                    )
                    
                    if status_message:
                        if image:
                            # To send a file with the edit, we need to delete the old message and send a new one
                            # since Discord doesn't allow editing messages to add files
                            await status_message.delete()
                            status_message = await ctx.send(formatted_msg, file=discord.File(fp=image, filename="verified.png"))
                        else:
                            await status_message.edit(content=formatted_msg)
                    else:
                        if image:
                            status_message = await ctx.send(formatted_msg, file=discord.File(fp=image, filename="verified.png"))
                        else:
                            status_message = await ctx.send(formatted_msg)
                
                # Remove from active verifications dictionary
                if user_id in active_verifications:
                    del active_verifications[user_id]
                    
                return
            except Exception as e:
                # Get message from messages.json or use default
                error_msg = MESSAGES.get('verification_process', {}).get('error', "{mention} Error assigning role: {error}")
                formatted_msg = error_msg.format(
                    mention=ctx.author.mention,
                    error=str(e)
                )
                
                # Edit existing message instead of sending a new one
                if status_message:
                    await status_message.edit(content=formatted_msg)
                else:
                    status_message = await ctx.send(formatted_msg)
                
                if user_id in active_verifications:
                    del active_verifications[user_id]
                return
        
        # Wait interval before next verification
        await asyncio.sleep(VERIFICATION_INTERVAL)
    
    # Time expired
    if user_id in active_verifications:
        # Get message from messages.json or use default
        expired_msg = MESSAGES.get('verification_process', {}).get('expired', "{mention} Verification time expired. Use `{prefix}{command} {habbo_user}` to try again.")
        formatted_msg = expired_msg.format(
            mention=ctx.author.mention,
            prefix=PREFIX,
            command=VERIFY_COMMAND,
            habbo_user=result['exact_name']
        )
        
        if status_message:
            await status_message.edit(content=formatted_msg)
        else:
            await ctx.send(formatted_msg)
        
        del active_verifications[user_id]

@bot.command(name=VERIFY_COMMAND)
async def verify(ctx, habbo_user=None):
    if habbo_user is None:
        # Get message from messages.json or use default
        no_username_msg = MESSAGES.get('verify', {}).get('no_username', "{mention} You need to provide your Habbo username. Example: `{prefix}{command} YourHabboUser`")
        await ctx.send(no_username_msg.format(
            mention=ctx.author.mention,
            prefix=PREFIX,
            command=VERIFY_COMMAND
        ))
        return
    
    user_id = ctx.author.id
    
    # Check if user already has a verification in progress
    if user_id in active_verifications:
        # Get message from messages.json or use default
        already_in_progress_msg = MESSAGES.get('verify', {}).get('already_in_progress', "{mention} You already have a verification in progress. Use `{prefix}cancel` to cancel.")
        formatted_msg = already_in_progress_msg.format(
            mention=ctx.author.mention,
            prefix=PREFIX
        )
        
        # Edit existing message instead of sending a new one
        existing_message = active_verifications[user_id].get('message')
        if existing_message:
            await existing_message.edit(content=formatted_msg)
        else:
            await ctx.send(formatted_msg)
        return
    
    # Generate verification code
    code = generate_code()
    
    # Get instructions message from messages.json or use default
    instructions_msg = MESSAGES.get('verify', {}).get('instructions', "{mention} Starting verification for Habbo user **{habbo_user}**\n\n**Instructions:**\n1. Access your Habbo account\n2. Change your motto to: `{code}`\n3. Wait for automatic verification\n\nVerification will expire in {expiration_minutes} minutes. Use `{prefix}cancel` to cancel the process.")
    
    # Format the message with the appropriate values
    formatted_msg = instructions_msg.format(
        mention=ctx.author.mention,
        habbo_user=habbo_user,
        code=code,
        expiration_minutes=EXPIRATION_TIME//60,
        prefix=PREFIX
    )
    
    # Send instructions and store the message to edit it later
    message = await ctx.send(formatted_msg)
    
    # Start verification process
    task = asyncio.create_task(verification_process(ctx, user_id, habbo_user, code))
    active_verifications[user_id] = {
        'habbo_user': habbo_user,
        'code': code,
        'expires_at': datetime.now() + timedelta(seconds=EXPIRATION_TIME),
        'task': task,
        'message': message
    }

@bot.command(name="cancel")
async def cancel(ctx):
    user_id = ctx.author.id
    
    if user_id in active_verifications:
        # Get existing message
        existing_message = active_verifications[user_id].get('message')
        
        # Cancel task
        active_verifications[user_id]['task'].cancel()
        
        # Get message from messages.json or use default
        success_msg = MESSAGES.get('cancel', {}).get('success', "{mention} Your verification has been cancelled.")
        formatted_msg = success_msg.format(
            mention=ctx.author.mention
        )
        
        # Edit existing message or send a new one
        if existing_message:
            await existing_message.edit(content=formatted_msg)
        else:
            await ctx.send(formatted_msg)
            
        del active_verifications[user_id]
    else:
        # Get message from messages.json or use default
        no_verification_msg = MESSAGES.get('cancel', {}).get('no_verification', "{mention} You don't have any verification in progress.")
        formatted_msg = no_verification_msg.format(
            mention=ctx.author.mention
        )
        await ctx.send(formatted_msg)

@bot.command(name="restart")
async def restart(ctx):
    user_id = ctx.author.id
    
    if user_id in active_verifications:
        habbo_user = active_verifications[user_id]['habbo_user']
        existing_message = active_verifications[user_id].get('message')
        
        # Cancel current task
        active_verifications[user_id]['task'].cancel()
        
        # If there's an existing message, update it informing restart
        if existing_message:
            # Get message from messages.json or use default
            in_progress_msg = MESSAGES.get('restart', {}).get('in_progress', "{mention} Restarting verification for user **{habbo_user}**...")
            formatted_msg = in_progress_msg.format(
                mention=ctx.author.mention,
                habbo_user=habbo_user
            )
            await existing_message.edit(content=formatted_msg)
            
            # Remove current verification
            del active_verifications[user_id]
            
            # Generate new code
            code = generate_code()
            
            # Get message from messages.json or use default
            instructions_msg = MESSAGES.get('restart', {}).get('instructions', "{mention} Restarting verification for Habbo user **{habbo_user}**\n\n**Instructions:**\n1. Access your Habbo account\n2. Change your motto to: `{code}`\n3. Wait for automatic verification (we check every {interval} seconds)\n\nVerification will expire in {expiration_minutes} minutes. Use `{prefix}cancel` to cancel the process.")
            formatted_msg = instructions_msg.format(
                mention=ctx.author.mention,
                habbo_user=habbo_user,
                code=code,
                interval=VERIFICATION_INTERVAL,
                expiration_minutes=EXPIRATION_TIME//60,
                prefix=PREFIX
            )
            
            # Update message with new instructions
            await existing_message.edit(content=formatted_msg)
            
            # Start new verification process
            task = asyncio.create_task(verification_process(ctx, user_id, habbo_user, code))
            active_verifications[user_id] = {
                'habbo_user': habbo_user,
                'code': code,
                'expires_at': datetime.now() + timedelta(seconds=EXPIRATION_TIME),
                'task': task,
                'message': existing_message
            }
        else:
            # If no existing message, remove verification and call verify command again
            del active_verifications[user_id]
            await ctx.invoke(bot.get_command(VERIFY_COMMAND), habbo_user=habbo_user)
    else:
        # Get message from messages.json or use default
        no_verification_msg = MESSAGES.get('restart', {}).get('no_verification', "{mention} You don't have any verification in progress to restart.")
        formatted_msg = no_verification_msg.format(
            mention=ctx.author.mention
        )
        await ctx.send(formatted_msg)

# Start the bot
# Check if token exists before running the bot
if TOKEN is None:
    raise ValueError("Discord token not found in environment variables")
bot.run(TOKEN)