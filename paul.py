import os
import random
import logging
import yaml
import discord
from discord.ext import commands
from dotenv import load_dotenv
import time
import pymongo
import re

version = "0.2pre1"
#TODO docstrigs
#init
#logging
timestr = time.strftime("%Y%m%d-%H%M%S")
logging.basicConfig(filename=f"Logs/debug-{timestr}.log",level=logging.DEBUG)
logging.info("Log Start")
#oauth
load_dotenv()
token = os.getenv('DISCORD_TOKEN')#load Oauth
#config load
if "config.yaml" not in os.listdir("./"):#check to see if a config file exists
    os.system("cp config.defaults config.yaml")#create config from template (if it doesnt exist)
with open("config.yaml") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)
#config init
imgParentDir = config["imageFolder"]
imgChildDirs = config["imageSubfolders"]
petpetpetDir = config["lotteryFolder"]
dbAddr = config["databaseAddress"]
bot = commands.Bot(command_prefix=config["commandPrefix"])
defaultCat = config["defaultCat"]
#mongo init
client = pymongo.MongoClient(f"mongodb://{dbAddr}/")
db = client.paulDB
settings = db.settings
users = db.users

@bot.event
async def on_ready():#confirms init
    print(f"{bot.user.name} Initialized and connected to Discord.")
    logging.info("Bot Connected to Discord")

@bot.command(name = "meow")#sends gib food
async def meow(ctx):
    createUser(ctx.author.id)
    logging.info("Meow command")
    await ctx.send("MEEEEEEOOOOOOWWWW!!!!!!!   *Translation*: **GIB FOOD!**")
    iterateCmd(ctx, "meow")

@bot.command(name = "info")#TODO Info command
async def info(ctx,user = ""):
    embed = discord.Embed(title = "Info!", description = "Disorganized stats for almost everything Paul! (and paul accessories)", color = 0x672aff)
    embed.set_thumbnail(url = "https://i.imgur.com/hPmQF6m.jpg")
    embed.set_author(name = "PaulBot",url = "https://github.com/TheJKL/PaulBot",icon_url = "https://i.imgur.com/hPmQF6m.jpg")
    embed.set_footer(text = f"paulBot v{version}", icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Octicons-mark-github.svg/1200px-Octicons-mark-github.svg.png")
    if (re.match(r"<@!\d{0,}>",user)):#if user doesnt exist, create it
        createUser(int(user[3:-1]))
    if (re.match(r"<@!\d{0,}>",user) and db.users.find({"uuid":int(user[3:-1])})):#making sure user is in the db, regex ensures it is an actual user (could be tricked)
        embed.add_field(name = "user", value = f"{user}")
        user = int(user[3:-1])
        userDoc = db.users.find_one({"uuid":user})["totals"]
        embed.add_field(name = "food",value = int(db.users.find_one({"uuid":user})["food"]))
    else:
        embed.add_field(name = "No User", value = "Overall Totals")
        for cat in imgChildDirs:#iterates through each cat and adds their image total to the embed
            embed.add_field(name = f"{cat} Pics", value = getTotalImages(cat))
        user = "totals"
        userDoc = db.users.find_one({"uuid":user})["totals"]

    
    for cmd,dic in userDoc.items():#iterates through commands and cats
        for cat,num in dic.items():
            embed.add_field(name = f"{cmd} {cat}", value = f"{num}")
    embed.add_field(name = "Report a Bug", value = "[Here](https://github.com/TheJKL/PaulBot/issues)", inline = False)
    await ctx.send(embed = embed)

@bot.command(name = "pet")#sends random image of paul
async def petCat(ctx, cat = "", numImg = 1):
    createUser(ctx.author.id)
    logging.info("Pet Command")
    numImg = int(numImg)
    cat = checkCat(cat)
    db.users.update_one({"uuid":ctx.author.id},{"$inc":{"food":50*numImg}})#TEMP way of getting food
    imgs = os.listdir(f"{imgParentDir}/{cat}")#list of image files in the Paul folder
    img = discord.File(f"{imgParentDir}/{cat}/{random.choice(imgs)}")
    await sendImage(ctx,img,cat)
    iterateCmd(ctx,"pet",cat)

@bot.command(name = "petpetpet")#paul lottery command 
async def petpetpet(ctx, cat = "",  numImg = 3):
    createUser(ctx.author.id)
    if numImg > 10:#limit petpetpet images to 10 - 1 per command call
        numImg = 3
        await ctx.send("HISSSSSS!!!   *Translation*: **!!ERROR CUTENESS OVERLOAD!!**")
    
    cat = checkCat(cat)
    
    logging.info(f"PetPetPet Command, NumImg = {numImg}, cat = {cat}")
    imgDir = os.listdir(f"{imgParentDir}/{cat}")
    imgs = []
    for _ in range(20):
        imgs.append(random.choice(imgDir))
    img = []

    for _ in range(numImg):#chooses images to send
        rand = random.choice(imgs)
        image = discord.File(f"{imgParentDir}/{cat}/{rand}")
        img.append(str(rand))
        await sendImage(ctx,image,cat)

    embed = discord.Embed(description = "", color = 0x672aff)
    if all(image == img[0] for image in img):#TODO add responses for two of a kind (or some percantage threshhold)
        embed.add_field(name  = "PetPetPet!", value = "**YOU WON!!!**")
    else:
        embed.add_field(name  = "PetPetPet!", value = "**You Lost!**")
    await ctx.send(embed = embed)
    iterateCmd(ctx,"petpetpet",cat)

@bot.command(name = "feed")#feeds a cat an ammount of food
async def feed(ctx, cat = "", numFood = 1):
    numFood = int(abs(numFood))#make sure the amount of food is a positive integer value
    cat = checkCat(cat)
    createUser(ctx.author.id)
    user = db.users.find_one({"uuid":ctx.author.id})
    logging.info(f"feed command, cat = {cat}, numFood = {numFood}")
    if not user["food"] < numFood:#checks if user has the amount of food they want to feed the cat
        if numFood < 100:#Nom limiter
            await ctx.send("Nom"*numFood)
        else:
            await ctx.send(":regional_indicator_n: :regional_indicator_o: :regional_indicator_m:")
        
        db.users.update_one({"uuid":"totals"},{"$inc":{f"totals.food.{cat}":numFood}})#increment food fed to cats
        db.users.update_one({"uuid":ctx.author.id},{"$inc":{"food":-1*numFood}})#remove food from user
        db.users.update_one({"uuid":ctx.author.id},{"$inc":{f"totals.food.{cat}":numFood}})#track how much food a user has fed
    else:
        await ctx.send("MEOWWWWW   *Translation*: **You don't have that much food.**")
    iterateCmd(ctx,"feed",cat)

def createUser(uuid):#creates a doc for a specified uuid
    if not users.count_documents({"uuid":uuid}):#if the user exists a user wont be created
        users.insert_one({
            "uuid" : uuid,
            "food" : 500,
            "totals" : {}
            })

async def sendImage(ctx,img,cat):#sends the specified image and iterates the totals for sent images
    await ctx.send(file = img)
    db.users.update_one({"uuid":"totals"},{"$inc":{f"totals.sentImg.{cat}":1}})
    db.users.update_one({"uuid":ctx.author.id},{"$inc":{f"totals.sentImg.{cat}":1}})

def iterateCmd(ctx,cmd,cat = defaultCat):#iterates the command in totals and for specific users
    db.users.update_one({"uuid":ctx.author.id},{"$inc":{f"totals.{cmd}.{cat}":1}})
    db.users.update_one({"uuid":"totals"},{"$inc":{f"totals.{cmd}.{cat}":1}})

def checkCat(cat):#checks if the cat is part of approved cats
    if cat.capitalize() not in imgChildDirs:
        cat = defaultCat#returns default cat if it isnt
    else:
        cat = cat.capitalize()#returns standard cat if it is
    return cat

def getTotalImages(cat):
    """Returns the total number of images stored in a cats director"""
    return len(os.listdir(f"{imgParentDir}/{checkCat(cat)}"))

bot.run(token)