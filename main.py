import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timedelta
import asyncio

# Bot configuration - CORRECTED TOKEN
TOKEN = 'MTQyMTA0NTQ2NzIzMTI4OTQwNg.GRbTjf.IL8-G_9AAzJziWbPYeqg1S7Mq48TQ9awAoCl8g'
PREFIX = '$'

# Enable all intents for full functionality
intents = discord.Intents.all()

# Create bot instance
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Data storage - In production, use a database
stock_data = {}  # Format: {"service_name": ["code1", "code2", ...]}
cooldowns = {}  # Format: {"user_id": {"service": datetime_object}}

# Configuration
COOLDOWN_TIME = 3600  # 1 hour cooldown in seconds

# Load data from file if exists
def load_data():
    global stock_data, cooldowns
    try:
        if os.path.exists('bot_data.json'):
            with open('bot_data.json', 'r') as f:
                data = json.load(f)
                stock_data = data.get('stock', {})
                # Convert cooldown timestamps back to datetime objects
                cooldowns_raw = data.get('cooldowns', {})
                cooldowns = {}
                for user_id, services in cooldowns_raw.items():
                    cooldowns[user_id] = {}
                    for service, timestamp in services.items():
                        cooldowns[user_id][service] = datetime.fromisoformat(timestamp)
    except Exception as e:
        print(f"Error loading data: {e}")
        stock_data = {}
        cooldowns = {}

# Save data to file
def save_data():
    try:
        # Convert datetime objects to strings for JSON serialization
        cooldowns_serializable = {}
        for user_id, services in cooldowns.items():
            cooldowns_serializable[user_id] = {}
            for service, dt in services.items():
                cooldowns_serializable[user_id][service] = dt.isoformat()
        
        data = {
            'stock': stock_data,
            'cooldowns': cooldowns_serializable
        }
        with open('bot_data.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

# Check if user is on cooldown
def check_cooldown(user_id, service):
    if str(user_id) not in cooldowns:
        return False
    if service not in cooldowns[str(user_id)]:
        return False
    
    cooldown_end = cooldowns[str(user_id)][service] + timedelta(seconds=COOLDOWN_TIME)
    return datetime.now() < cooldown_end

# Set cooldown for user
def set_cooldown(user_id, service):
    if str(user_id) not in cooldowns:
        cooldowns[str(user_id)] = {}
    cooldowns[str(user_id)][service] = datetime.now()

@bot.event
async def on_ready():
    print(f'✅ {bot.user.name} is online and ready!')
    print(f'🤖 Bot ID: {bot.user.id}')
    print(f'📡 Connected to {len(bot.guilds)} servers')
    
    # Load existing data
    load_data()
    
    # Start auto-save task
    auto_save.start()
    
    # Set bot status
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"{PREFIX}genhelp for commands")
    await bot.change_presence(status=discord.Status.online, activity=activity)

# Auto-save data every 5 minutes
@tasks.loop(minutes=5)
async def auto_save():
    save_data()
    print("📊 Data auto-saved")

@auto_save.before_loop
async def before_auto_save():
    await bot.wait_until_ready()

# Error handling
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"❌ Error in {event}: {args}, {kwargs}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument. Use `{PREFIX}genhelp` for command usage.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        print(f"Command error: {error}")

# USER COMMANDS

@bot.command(name='gen')
async def generate_code(ctx, service=None):
    """Generate a demo/service code for the specified service"""
    if not service:
        embed = discord.Embed(
            title="❌ Missing Service",
            description=f"Please specify a service name.\n\n**Usage:** `{PREFIX}gen <service>`\n**Example:** `{PREFIX}gen netflix`",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    service = service.lower()
    user_id = str(ctx.author.id)
    
    # Check if service exists
    if service not in stock_data or not stock_data[service]:
        embed = discord.Embed(
            title="📦 Out of Stock",
            description=f"Sorry, **{service}** is currently out of stock.\n\nUse `{PREFIX}stock` to see available services.",
            color=0xffa500
        )
        await ctx.send(embed=embed)
        return
    
    # Check cooldown
    if check_cooldown(ctx.author.id, service):
        cooldown_end = cooldowns[user_id][service] + timedelta(seconds=COOLDOWN_TIME)
        time_left = cooldown_end - datetime.now()
        minutes_left = int(time_left.total_seconds() / 60)
        
        embed = discord.Embed(
            title="⏰ Cooldown Active",
            description=f"You need to wait **{minutes_left} minutes** before requesting another **{service}** code.",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    # Get a code
    code = stock_data[service].pop(0)
    set_cooldown(ctx.author.id, service)
    
    # Send code via DM
    try:
        dm_embed = discord.Embed(
            title="🎁 Your Demo/Service Code",
            description=f"**Service:** {service.title()}\n**Code:** `{code}`\n\n⚠️ Keep this code private and use it responsibly.",
            color=0x00ff00
        )
        dm_embed.set_footer(text=f"Generated from {ctx.guild.name}")
        await ctx.author.send(embed=dm_embed)
        
        # Confirmation in channel
        embed = discord.Embed(
            title="✅ Code Sent!",
            description=f"Your **{service}** code has been sent to your DMs!\n\n📊 **Remaining stock:** {len(stock_data[service])}",
            color=0x00ff00
        )
        await ctx.send(embed=embed)
        
    except discord.Forbidden:
        # If DM fails, send in channel with deletion
        embed = discord.Embed(
            title="🎁 Your Demo/Service Code",
            description=f"**Service:** {service.title()}\n**Code:** `{code}`\n\n⚠️ This message will be deleted in 30 seconds for security.",
            color=0x00ff00
        )
        message = await ctx.send(embed=embed)
        await asyncio.sleep(30)
        try:
            await message.delete()
        except:
            pass
    
    save_data()

@bot.command(name='stock')
async def view_stock(ctx):
    """View available stock and services"""
    if not stock_data:
        embed = discord.Embed(
            title="📦 Stock Status",
            description="No services are currently in stock.\n\nAdmins can add stock using the `$restock` command.",
            color=0xffa500
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="📦 Current Stock",
        description="Here are all available services and their stock counts:",
        color=0x0099ff
    )
    
    total_items = 0
    for service, codes in stock_data.items():
        count = len(codes)
        total_items += count
        status_emoji = "✅" if count > 0 else "❌"
        embed.add_field(
            name=f"{status_emoji} {service.title()}",
            value=f"**{count}** codes available",
            inline=True
        )
    
    embed.set_footer(text=f"Total items in stock: {total_items}")
    await ctx.send(embed=embed)

@bot.command(name='genhelp')
async def gen_help(ctx):
    """Display help information and usage"""
    embed = discord.Embed(
        title="🤖 24/7 Utility Bot - Help",
        description="Here are all the commands you can use:",
        color=0x0099ff
    )
    
    # User commands
    embed.add_field(
        name="👤 User Commands",
        value=f"`{PREFIX}gen <service>` - Request a demo/service code\n"
              f"`{PREFIX}stock` - View available stock\n"
              f"`{PREFIX}genhelp` - Show this help message",
        inline=False
    )
    
    # Check if user is admin
    if ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_messages:
        embed.add_field(
            name="⚙️ Admin Commands",
            value=f"`{PREFIX}restock <service>` - Add codes to a service\n"
                  f"`{PREFIX}drop <service> <amount>` - Drop codes publicly\n"
                  f"`{PREFIX}clearstock <service>` - Clear all codes\n"
                  f"`{PREFIX}removecooldown <member> <service>` - Remove cooldown\n"
                  f"`{PREFIX}cmdlist_admin` - Show detailed admin commands",
            inline=False
        )
    
    embed.add_field(
        name="ℹ️ Information",
        value=f"• **Cooldown:** 1 hour per service\n"
              f"• **Codes:** Sent via DM for privacy\n"
              f"• **Status:** 24/7 online with auto-reconnect",
        inline=False
    )
    
    embed.set_footer(text=f"Bot Prefix: {PREFIX} | Made for safe code distribution")
    await ctx.send(embed=embed)

# ADMIN COMMANDS

def is_admin():
    def predicate(ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_messages
    return commands.check(predicate)

@bot.command(name='restock')
@is_admin()
async def restock_service(ctx, service=None):
    """Add new codes to a service (Admin only)"""
    if not service:
        embed = discord.Embed(
            title="❌ Missing Service",
            description=f"Please specify a service name.\n\n**Usage:** `{PREFIX}restock <service>`\n**Example:** `{PREFIX}restock netflix`",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    service = service.lower()
    
    embed = discord.Embed(
        title="📝 Add Codes",
        description=f"Please send the codes for **{service}** (one per line).\n\n⚠️ Send `cancel` to cancel this operation.\n⏱️ You have 5 minutes to respond.",
        color=0x0099ff
    )
    await ctx.send(embed=embed)
    
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel
    
    try:
        response = await bot.wait_for('message', check=check, timeout=300)
        
        if response.content.lower() == 'cancel':
            await ctx.send("❌ Restock operation cancelled.")
            return
        
        codes = [code.strip() for code in response.content.split('\n') if code.strip()]
        
        if not codes:
            await ctx.send("❌ No valid codes found.")
            return
        
        if service not in stock_data:
            stock_data[service] = []
        
        initial_count = len(stock_data[service])
        stock_data[service].extend(codes)
        
        embed = discord.Embed(
            title="✅ Restock Complete",
            description=f"**Service:** {service.title()}\n"
                       f"**Added:** {len(codes)} codes\n"
                       f"**Total Stock:** {len(stock_data[service])} codes",
            color=0x00ff00
        )
        await ctx.send(embed=embed)
        
        save_data()
        
        # Delete the codes message for security
        try:
            await response.delete()
        except:
            pass
            
    except asyncio.TimeoutError:
        await ctx.send("⏱️ Restock operation timed out.")

@bot.command(name='drop')
@is_admin()
async def drop_codes(ctx, service=None, amount=None):
    """Drop codes publicly in the channel (Admin only)"""
    if not service or not amount:
        embed = discord.Embed(
            title="❌ Missing Arguments",
            description=f"Please specify service and amount.\n\n**Usage:** `{PREFIX}drop <service> <amount>`\n**Example:** `{PREFIX}drop netflix 3`",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    service = service.lower()
    
    try:
        amount = int(amount)
    except ValueError:
        await ctx.send("❌ Amount must be a number.")
        return
    
    if service not in stock_data or len(stock_data[service]) < amount:
        available = len(stock_data.get(service, []))
        await ctx.send(f"❌ Not enough stock. Available: {available}, Requested: {amount}")
        return
    
    dropped_codes = []
    for _ in range(amount):
        if stock_data[service]:
            dropped_codes.append(stock_data[service].pop(0))
    
    embed = discord.Embed(
        title="🎁 Code Drop!",
        description=f"**Service:** {service.title()}\n**Codes:** {amount}\n\n" + "\n".join([f"`{code}`" for code in dropped_codes]),
        color=0xffd700
    )
    embed.set_footer(text="First come, first served! Use codes responsibly.")
    await ctx.send(embed=embed)
    
    save_data()

@bot.command(name='clearstock')
@is_admin()
async def clear_stock(ctx, service=None):
    """Clear all codes from a service (Admin only)"""
    if not service:
        embed = discord.Embed(
            title="❌ Missing Service",
            description=f"Please specify a service name.\n\n**Usage:** `{PREFIX}clearstock <service>`\n**Example:** `{PREFIX}clearstock netflix`",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    service = service.lower()
    
    if service not in stock_data:
        await ctx.send(f"❌ Service **{service}** not found.")
        return
    
    cleared_count = len(stock_data[service])
    stock_data[service] = []
    
    embed = discord.Embed(
        title="🗑️ Stock Cleared",
        description=f"**Service:** {service.title()}\n**Cleared:** {cleared_count} codes",
        color=0xff0000
    )
    await ctx.send(embed=embed)
    
    save_data()

@bot.command(name='removecooldown')
@is_admin()
async def remove_cooldown(ctx, member: discord.Member = None, service=None):
    """Remove cooldown for a member (Admin only)"""
    if not member or not service:
        embed = discord.Embed(
            title="❌ Missing Arguments",
            description=f"Please specify member and service.\n\n**Usage:** `{PREFIX}removecooldown <@member> <service>`\n**Example:** `{PREFIX}removecooldown @user netflix`",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    service = service.lower()
    user_id = str(member.id)
    
    if user_id in cooldowns and service in cooldowns[user_id]:
        del cooldowns[user_id][service]
        if not cooldowns[user_id]:  # Remove user if no cooldowns left
            del cooldowns[user_id]
        
        embed = discord.Embed(
            title="✅ Cooldown Removed",
            description=f"Removed **{service}** cooldown for {member.mention}",
            color=0x00ff00
        )
        await ctx.send(embed=embed)
        save_data()
    else:
        await ctx.send(f"❌ {member.mention} has no active cooldown for **{service}**.")

@bot.command(name='cmdlist_admin')
@is_admin()
async def admin_command_list(ctx):
    """Display detailed admin command list"""
    embed = discord.Embed(
        title="⚙️ Admin Commands - Detailed Guide",
        description="Here are all admin commands with detailed usage:",
        color=0xff6600
    )
    
    embed.add_field(
        name=f"{PREFIX}restock <service>",
        value="Add new codes to a service. Bot will ask you to send codes (one per line).",
        inline=False
    )
    
    embed.add_field(
        name=f"{PREFIX}drop <service> <amount>",
        value="Drop specified amount of codes publicly in the channel for everyone to grab.",
        inline=False
    )
    
    embed.add_field(
        name=f"{PREFIX}clearstock <service>",
        value="Remove all codes from a specific service. Use with caution!",
        inline=False
    )
    
    embed.add_field(
        name=f"{PREFIX}removecooldown <@member> <service>",
        value="Remove cooldown for a specific user and service combination.",
        inline=False
    )
    
    embed.set_footer(text="⚠️ Admin commands require Manage Messages or Administrator permissions")
    await ctx.send(embed=embed)

# Auto-reconnect and error recovery
@bot.event
async def on_disconnect():
    print("⚠️ Bot disconnected. Attempting to reconnect...")

@bot.event
async def on_resumed():
    print("✅ Bot reconnected successfully!")

# Run the bot with auto-reconnect
if __name__ == "__main__":
    print("🚀 Starting 24/7 Utility Bot...")
    print("📋 Features: Code Generation, Stock Management, Admin Controls")
    print("⚡ Auto-reconnect enabled for 24/7 uptime")
    
    # Run bot with the token
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        print("Check your Discord token and try again.")