import logging
import asyncio
import discord
import random
import os
import sys
from discord.ext import commands

from discord import VoiceClient
from discord import opus

#loading opus is required for VOICE to work
if not opus.is_loaded():
    # the 'opus' library here is opus.dll on windows
    # or libopus.so on linux in the current directory
    # you should replace this with the location the
    # opus library is located in and with the proper filename.
    # note that on windows this DLL is automatically provided for you
    opus.load_opus('opus')


print("[+]\tSETTING UP LOGGING")
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)
print("[+]\tDONE")

#--------------MAIN BOT-----------------#

bot = commands.Bot(command_prefix='?', description="")


@bot.event
async def on_ready():
    print("Logged in as " + bot.user.name + "@" + bot.user.id)
    print("----------------------------------------------------")

# check for argument instead?

#-----------TEXT COMMANDS---------------#
class NonMusic:
    """non music related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.RATO_LIST = [
                            "Yes",
                            "No",
                            "Maybe some day",
                            "Completely immoral",
                            "You'll need a fedora",
                            "Suicide is the only option",
                            "Buy a pet rat instead",
                            "Smoke salvia then ask again",
                            "Work hard at it",
                            "I'm going to behead you with a knife in your sleep for asking that"]


    """async def arg_check(msg, args):
        msgList = msg.split()
        if (len(msgList)-1) != args:
            await bot.say("not enough arguments")
            return False
        else:
            return True"""
            
    @commands.command()
    async def hello(self):
        await self.bot.reply("hello i am rato", tts=True)

    @commands.command()
    async def ask(self, question : str):
        """| ask rato for life advice"""
        # if question != False:
        await self.bot.reply(random.choice(self.RATO_LIST), tts=True)

    # convert string to integer, raise exception if not work and display how program work
    @commands.command()
    async def roll(self, Min : str, Max : str):
        """| rolls dice"""
        await self.bot.say(random.randint(int(Min), int(Max))) 

    @commands.command(pass_context=True)
    async def shutdown(self, ctx):
        """| shutsdown bot"""
        await self.bot.say(":rat: bot out")
        logging.shutdown()
        await self.bot.logout()
        await self.bot.close()
                         
    @commands.command(pass_context=True)
    async def restart(self, ctx):
        """| restarts bot, only works if you start bot outside of IDE (editor)"""
        await self.bot.say("brb, changing to underwear :wink:", tts=True)
        logging.shutdown()
        await self.bot.logout()
        await self.bot.close()
        os.execv(sys.executable, ['python'] + sys.argv)    

bot.add_cog(NonMusic(bot))
    
#------------VOICE CLIENT------------#

class VoiceEntry:
    def __init__(self, message, player):
        self.requester = message.author
        self.channel = message.channel
        self.player = player

    def __str__(self):
        fmt = '*{0.title}* uploaded by {0.uploader} and requested by {1.display_name}'
        duration = self.player.duration
        if duration:
            fmt = fmt + ' [length: {0[0]}m {0[1]}s]'.format(divmod(duration, 60))
        return fmt.format(self.player, self.requester)

class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
        self.bot = bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.skip_votes = set() # a set of user_ids that voted
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False

        player = self.current.player
        return not player.is_done()

    @property
    def player(self):
        return self.current.player

    def skip(self):
        self.skip_votes.clear()
        if self.is_playing():
            self.player.stop()

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.songs.get()
            await self.bot.send_message(self.current.channel, 'Now playing ' + str(self.current))
            self.current.player.start()
            await self.play_next_song.wait()

class Music:
    """voice related commands.
    works in multiple servers at once.
    """
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_states[server.id] = state

        return state

    async def create_voice_client(self, channel):
        voice = await self.bot.join_voice_channel(channel)
        state = self.get_voice_state(channel.server)
        state.voice = voice

    def __unload(self):
        for state in self.voice_states.values():
            try:
                state.audio_player.cancel()
                if state.voice:
                    self.bot.loop.create_task(state.voice.disconnect())
            except:
                pass

    @commands.command(pass_context=True, no_pm=True)
    async def join(self, ctx, *, channel : discord.Channel):
        """| joins a voice channel."""
        try:
            await self.create_voice_client(channel)
        except discord.ClientException:
            await self.bot.say('Already in a voice channel...')
        except discord.InvalidArgument:
            await self.bot.say('This is not a voice channel...')
        else:
            await self.bot.say('Ready to play audio in ' + channel.name)

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """| summons the bot to join your voice channel."""
        summoned_channel = ctx.message.author.voice_channel
        if summoned_channel is None:
            await self.bot.say('You are not in a voice channel.')
            return False

        state = self.get_voice_state(ctx.message.server)
        if state.voice is None:
            state.voice = await self.bot.join_voice_channel(summoned_channel)
        else:
            await state.voice.move_to(summoned_channel)

        return True

    @commands.command(pass_context=True, no_pm=True)
    async def play(self, ctx, *, song : str):
        """| plays a song.
        If there is a song currently in the queue, then it is
        queued until the next song is done playing.
        This command automatically searches as well from YouTube.
        The list of supported sites can be found here:
        https://rg3.github.io/youtube-dl/supportedsites.html
        """
        state = self.get_voice_state(ctx.message.server)
        opts = {
            'default_search': 'auto',
            'quiet': True,
        }
        beforeArgs = " -reconnect 1" 

        if state.voice is None:
            success = await ctx.invoke(self.summon)
            if not success:
                return

        try:
            player = await state.voice.create_ytdl_player(song, ytdl_options=opts, after=state.toggle_next, before_options=beforeArgs)
        except Exception as e:
            fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
            await self.bot.send_message(ctx.message.channel, fmt.format(type(e).__name__, e))
        else:
            player.volume = 0.6
            entry = VoiceEntry(ctx.message, player)
            await self.bot.say('Enqueued ' + str(entry))
            await state.songs.put(entry)

    @commands.command(pass_context=True, no_pm=True)
    async def volume(self, ctx, value : int):
        """| sets the volume of the currently playing song."""

        state = self.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.volume = value / 100
            await self.bot.say('Set the volume to {:.0%}'.format(player.volume))

    @commands.command(pass_context=True, no_pm=True)
    async def pause(self, ctx):
        """| pauses the currently played song."""
        state = self.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.pause()

    @commands.command(pass_context=True, no_pm=True)
    async def resume(self, ctx):
        """| resumes the currently played song."""
        state = self.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.resume()

    @commands.command(pass_context=True, no_pm=True)
    async def stop(self, ctx):
        """| stops playing audio and leaves the voice channel.
        This also clears the queue.
        """
        server = ctx.message.server
        state = self.get_voice_state(server)

        if state.is_playing():
            player = state.player
            player.stop()

        try:
            state.audio_player.cancel()
            del self.voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass

    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        """| vote to skip a song. The song requester can automatically skip.
        2 skip votes are needed for the song to be skipped.
        """

        state = self.get_voice_state(ctx.message.server)
        if not state.is_playing():
            await self.bot.say('not playing any music')
            return

        voter = ctx.message.author
        if voter == state.current.requester:
            await self.bot.say('skipping soooong')
            state.skip()
        elif voter.id not in state.skip_votes:
            state.skip_votes.add(voter.id)
            total_votes = len(state.skip_votes)
            if total_votes >= 2:
                await self.bot.say('democracy has spoken, skipping soooong')
                state.skip()
            else:
                await self.bot.say('vote to skip added [{}/2]'.format(total_votes))
        else:
            await self.bot.say('you have already voted')

    @commands.command(pass_context=True, no_pm=True)
    async def playing(self, ctx):
        """Shows info about the currently played song."""

        state = self.get_voice_state(ctx.message.server)
        if state.current is None:
            await self.bot.say('not playing anything')
        else:
            skip_count = len(state.skip_votes)
            await self.bot.say('playing {} [skips: {}/2]'.format(state.current, skip_count))

    """@commands.command()
    async def flashbang(self, ctx, *, channel : discord.Channel)
        | flashbang a channel
        
        try:
            await self.create_voice_client(channel)
        except discord.InvalidArgument:
            await self.bot.say('cant find specified target...')
        else:
            await self.bot.say('Ready to play audio in ' + channel.name)"""


bot.add_cog(Music(bot))

#----------------------------------#

bot.run('') #insert secret token here
