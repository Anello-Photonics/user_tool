#try geotiler for user_program real time map function
#goal: make a map at some lat,lon, size and put an arrow with lat,lon,heading

import os
import contextlib
# with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
#     print("this should not print")
import geotiler
from geotiler.tile.io import fetch_tiles
from geotiler.cache import caching_downloader
from functools import partial
import PIL #for image tools
from PIL import Image, ImageFont, ImageDraw
import math
from matplotlib.font_manager import findSystemFonts
import asyncio

#specify arrow image to use. should be square proportions, arrow shape on transparent background
# image needs to have "alpha channel"  (transparency information?)
#arrow_file_name =  "A.png"
#arrow_file_name = "mini_arrow_clear.png"
#arrow_file_name = "big_chevron.png" #1024x1024 red/orange chevron, center is inner corner of chevron.


#lat, lon: coordinates to center the map on. arrow will go there too
#zoom: larger = closer in, 16 looks good for street maps
#map_size: (x,y) in pixels
#arrow_size: int size , arrow will be scaled to (size,size) bounding square. should be smaller than map dimensions
def draw_map(lat, lon, zoom, map_size, arrow_size, heading_deg, arrow_image_path, provider='osm', storage=None):
    #provider = 'bluemarble'
    map = geotiler.Map(center=(lon, lat), zoom=zoom, size=map_size, provider=provider) #note center is lon,lat order

    #image = geotiler.render_map(map)  #basic version with no caching scheme

    #put image into storage. todo - should it skip if already in storage? caching_downloader will call set anyway.
    #storage should be lru-dict, could be standard dict too (but then watch out for memory filling)

    def dictionary_set(url, image):
        #print("set: url = " + str(url) + ", image = " + str(type(image))+", size = "+str(len(image) if image else None))
        if storage is not None:
            storage[url] = image
            #print("tiles in storage: " + str(len(storage)))
        else:
            return None

    def dictionary_get(url):
        #print("get: url = "+str(url), end="")
        if (storage is not None) and (url in storage):
            #print(" ---> hit")
            return storage[url]
        #print(" ---> miss")
        return None

    #geotiler.cache.caching_downloader(get, set, downloader, tiles, num_workers, **kw)
    my_downloader = partial(caching_downloader, dictionary_get, dictionary_set, fetch_tiles)
    image = geotiler.render_map(map, downloader=my_downloader)

    #todo - any map settings like what things to show, language, colors, map scale etc?

    x, y = map.rev_geocode((lon, lat)) #center lon, lat to image pixels. note lon,lat order
    #print("center point in pixels: "+str((x, y)))

    #put arrow on the map using PIL image methods
    arrow = PIL.Image.open(arrow_image_path).resize((arrow_size, arrow_size))
    arrow_rotated = arrow.rotate(-1.0 * heading_deg) #heading and rotate function have opposite direction
    arrow_width, arrow_height = arrow_rotated.width, arrow_rotated.height
    #print("arrow image dimensions: "+str((arrow_width, arrow_height)))
    x_offset, y_offset = arrow_width/2, arrow_height/2
    arrow_corner_x, arrow_corner_y = x - x_offset, y - y_offset #must be in map, and it will be if scaled
    #print("arrow image upper left corner for destination: "+str((arrow_corner_x, arrow_corner_y)))

    #alpha composite: removes transparent background.
    #dest is upper left corner of the inserted image
    #checks if arrow corner goes outside the image. should not happen if we scale the arrow correctly.
    try:
        image.alpha_composite(arrow_rotated, dest=(int(arrow_corner_x), int(arrow_corner_y)))
    except ValueError as e:
        print("error placing arrow: may be too big or off the map.")
        print("error description = "+str(type(e))+" "+str(e))
    return image

#todo - make an "update" method for when position, heading, zoom change? Or just call draw_map over again?


def centered_circle(draw, center, radius, fill=None, outline=None, width=1):
    center_x, center_y = center
    draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius)
                 ,fill=fill,outline=outline, width=int(width))


#dial with arrow inside a square bounding area
#side_len: side length of the image in pixels
#angle_offset_deg: rotates the zero point of dial. if 0, zero point is to the right
#angle step_deg: degrees between ticks
#text_size: for numbers, in pixels. tried auto-scaling to image but too hard
#show_angle_deg: angle to point the needle at
#TODO - is it inefficient to draw this every time? Could save/load the dial and redraw the arrow only
def draw_dial(side_len, angle_offset_deg, angle_step_deg, dial_direction, text_size, show_angle_deg):
    #colors and other constants
    background_color = (255, 255, 255)
    line_color = (0, 0, 0)
    dial_color = (255, 255, 224)
    arrow_color = (255, 0, 0)

    #dimensions: make everything proportional to image size
    half_side = side_len / 2.0
    border_width = side_len * 0.14  #space between circle and square
    circle_radius = half_side - border_width
    numbers_radius = circle_radius + (border_width / 2.0)
    dot_width = side_len * 0.01

    try:
        #get font, works on windows but not pi. TODO - include a font file, or check available fonts?

        available_fonts = findSystemFonts(fontpaths=None, fontext='ttf')
        #take first available font by sort. windows got agencyb
        # todo- look for a preferred font first, and then pick a random one if not found?
        chosen_font = sorted(available_fonts)[0]
        #print(chosen_font)
        #numbers_font = ImageFont.truetype("arial.ttf", text_size) #text size is in pixels, so scale it with image
        numbers_font = ImageFont.truetype(chosen_font, text_size)  # text size is in pixels, so scale it with image
    except Exception as e:
        numbers_font = ImageFont.load_default() #need this as fallback, but then can't set a size. may be too small.
    text_anchor = 'mm' #place text by center

    dial_image = PIL.Image.new('RGBA', (side_len, side_len), background_color) #square white background
    draw = PIL.ImageDraw.Draw(dial_image)

    #main circle of dial
    centered_circle(draw, (half_side, half_side), circle_radius, outline=line_color, width=dot_width, fill=dial_color)

    #ticks and numbers around the circle
    num_steps = int(360 / angle_step_deg)
    for step in range(num_steps):
        theta_deg = step * angle_step_deg
        theta_deg_from_top = (theta_deg + angle_offset_deg) % 360 #turn by 90 degrees to put 0 at top.
        theta_deg_to_show = theta_deg_from_top if theta_deg_from_top <= 180 else theta_deg_from_top - 360
        theta_deg_to_show *= dial_direction
        theta_rad = (math.pi / 180)*theta_deg
        cosine, sine = math.cos(theta_rad), math.sin(theta_rad)
        dash_x, dash_y = circle_radius*cosine + half_side, circle_radius*sine + half_side
        numbers_x, numbers_y = numbers_radius*cosine + half_side, numbers_radius*sine + half_side

        centered_circle(draw, (dash_x, dash_y), dot_width, fill=line_color) #dots at increments. todo - make these rectangular dashes?
        #label the angles.
        draw.text((numbers_x, numbers_y), str(theta_deg_to_show), font=numbers_font, anchor=text_anchor, fill=line_color)

    #draw the arrow to the angle.
    show_angle_rad = (show_angle_deg - angle_offset_deg) * (math.pi/180) * dial_direction
    arrow_length = (numbers_radius + circle_radius) / 2
    arrow_end_x = arrow_length*math.cos(show_angle_rad) + half_side
    arrow_end_y = arrow_length*math.sin(show_angle_rad) + half_side
    draw.line([int(half_side), int(half_side), int(arrow_end_x), int(arrow_end_y)], fill=arrow_color, width=int(dot_width))

    #show the angle at the end of the indicator? or could put it in a fixed place.
    number_x = (numbers_radius + text_size/2) * math.cos(show_angle_rad) + half_side
    number_y = (numbers_radius + text_size/2) * math.sin(show_angle_rad) + half_side
    draw.text((number_x, number_y), '%.2f' % show_angle_deg, font=numbers_font, anchor=text_anchor, fill=arrow_color)  # font=numbers_font)

    # center dot: put on top of line?
    centered_circle(draw, (half_side, half_side), dot_width, fill=line_color, outline=line_color)
    return dial_image


#copied geotiler redis_downloader for reference: my downloader should do this but with different set/get functions
#or do I just call caching_downloader with my own set/get functions? but then I don't know other args.

# def redis_downloader(client, downloader=None, timeout=3600 * 24 * 7):
#     """
#     Create downloader using Redis as cache for map tiles.
#
#     :param client: Redis client object.
#     :param downloader: Map tiles downloader, use `None` for default downloader.
#     :param timeout: Map tile data expiry timeout, default 1 week.
#     """
#     if downloader is None:
#         downloader = fetch_tiles
#     set = lambda key, value: client.setex(key, timeout, value) if value is not None else None
#     return partial(caching_downloader, client.get, set, downloader)

#my version - does it need timeout?
#get:  return the tile from cache or None if not found.  calling:  img = get(t.url) where ti is tile object (?)
#set:  put something into cache. calling:  set(t.url, t.img) , where t is a tile object (?). return anything?

#geotiler.cache.caching_downloader(get, set, downloader, tiles, num_workers, **kw)
def dummy_downloader(client, downloader=None, timeout=3600 * 24 * 7):
    if downloader is None:
        downloader = fetch_tiles #I think this means regular download from internet

    #set = lambda key, value: client.setex(key, timeout, value) if value is not None else None

    #dummy_set = lambda url, image: print("set: "+str(url)+", "+str(image)); return None #or is there a "success" value I can fake?
    #dummy_get = lambda url : print("get: "+str(url)); return None #always fails to get

    def dummy_set(url, image):
        print("set: " + str(url) + ", " + str(image))
        return None

    def dummy_get(url):
        print("get: "+str(url))
        return None #always fails to get

    return partial(caching_downloader, dummy_get, dummy_set, downloader)

#can try defining a different "fetch" function to handle errors differently
# def log_error(tile):
#     if tile.error:
#         print('tile {} error: {}'.format(tile.url, tile.error)) #could remove the print, return None, etc
#     return tile
#
# async def fetch(mm):
#     tiles = geotiler.fetch_tiles(mm)
#     # process tile in error and then render all the tiles
#     tiles = (log_error(t) async for t in tiles) #should I error if any of them have error?
#     img = await geotiler.render_map_async(mm, tiles=tiles)
#     return img



if __name__ == "__main__":
    #note osm website and google maps are lat,lon but geotiler functions are lon,lat
    # zoom: bigger number is closer/more detail. 16 looks like a good scale for city driving. 10 is way too zoomed out.
    #min: 1 = whole earth square, max 19 = shows individual buildings
    #saw tiling load errors at zooms 1-5 , even 10 is too big

    #try caching:
    #geotiler.cache.caching_downloader(get, set, downloader, tiles, num_workers, **kw)[source]
    #get : function to get a tile, or return None if not in cache -> will download
    #set: function to put in cache
    #I can try making a get and set function - put into a data structure.
    #downloader - what it downloads with when not in cache - None for download from internet?
    #tiles: "Collection tiles to fetch" - what does that mean

    # dummy_get = lambda x: None
    # dummy_set = lambda x: None
    # cached_downloader = geotiler.cache.caching_downloader(get=dummy_get, set=dummy_set, downloader=None, tiles=None, num_workers=1)

    map_dict = {}
    #print("map_dict before: "+str(map_dict))

    #golden gate park kezar drive san francisco ca
    #draw_map(37.768036, -122.455932, 15, (500, 300), 50, -65)

    # Tel Aviv, Israel
    # Zeev Jabotinsky St, pointing away from the circular park
    image = draw_map(32.087148, 34.788035, 19, (2500, 1500), 50, 80, "big_chevron.png", provider='osm', storage=map_dict)
    #draw_map(lat, lon, zoom, dimensions, arrow_size, heading, arrow_file_name)

    #try different providers there
    #image = draw_map(32.087148, 34.788035, 16, (2500, 1500), 50, 80, "big_chevron.png", provider='osm')  # ok

    #bluemarble: looks like satellite but can't zoom in close. zoom levels 0-9, 9 is still way too far out.
    #image = draw_map(32.087148, 34.788035, 2, (1000, 1000), 50, 80, "big_chevron.png", provider='bluemarble')

    #stamen-terrain- maybe a good option
    #image = draw_map(32.087148, 34.788035, 18, (500, 500), 50, 80, "big_chevron.png", provider='stamen-terrain', storage=map_dict) #ok
    #print("do it again, see if cache hit.")
    #image2 = draw_map(32.087148, 34.788035, 18, (500, 500), 50, 80, "big_chevron.png", provider='stamen-terrain', storage=map_dict)

    #image = draw_map(31.006413, 35.144606, 13, (2500, 1500), 50, 80, "big_chevron.png", provider='stamen-toner') #ok

    #stamen-toner: complete load here, all black and white
    #image = draw_map(32.087148, 34.788035, 16, (2500, 1500), 50, 80, "big_chevron.png", provider='stamen-toner')

    # stamen-toner-lite: also complete, gray and white
    #image = draw_map(32.087148, 34.788035, 16, (2500, 1500), 50, 80, "big_chevron.png", provider='stamen-toner-lite')

    # stamen-watercolor: works, very colorful, no labels. so don't use this by itself. maybe with other layers.
    #image = draw_map(32.087148, 34.788035, 16, (2500, 1500), 50, 80, "big_chevron.png", provider='stamen-watercolor')

    # thunderforest-cycle: find_provider fails, not sure why it is in providers() then.
    #image = draw_map(32.087148, 34.788035, 16, (2500, 1500), 50, 80, "big_chevron.png", provider='thunderforest-cycle')

    #draw_map(32.096666, 34.789873, 16, (500, 300), 50, -80) #bike path next to Yarkon river

    #this errors at all zooms I tried - too close to pole? or is it invalid coords?
    #map = draw_map(88.27063522262247, 156.93487998560647, 1, (500, 500), 50, 129)

    #image = draw_dial(200, 90, 15, 10, 137.6) #500 or larger places the numbers reasonably.

    # todo try providers other than osm? see geotiler.providers(), geotiler.find_provider(id)
    #seems like osm or stamen-terrain are best. other stamen not so useful

    # geotiler.providers() showed me: ['bluemarble', 'osm',
    # 'stamen-terrain', 'stamen-terrain-background', 'stamen-terrain-lines', 'stamen-toner', 'stamen-toner-lite', 'stamen-watercolor',
    # 'thunderforest-cycle']
    # geotiler.find_provider() on those ids returns an object - do we need that?


    #osm: default, works
    #stamen: lots of different stamen layers, probably meant to combine them. not sure if I want to bother with that
        #stamen-terrain, toner, toner-lite, watercolor worked
        #stamen-terrain-background and stamen-terrain-lines both had some partial loads - only some tiles loaded
    #bluemarble - seems like I can't zoom in close, so not useful for navigation.
    #thunderforest-cycle: showed in providers() but didn't work for map call.

    image.save('map.png')
    image.show(title="Here is an arrow on a map")
    #print("map_dict after: " + str(map_dict.keys()))
