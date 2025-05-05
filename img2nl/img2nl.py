'''
given a circuit schematic image(hand drawn or computer generated),
it will return the netlist of the circuit.
'''

from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_dilation
import numpy as np
import time

from my_utils import img_preprocess, skeletonize_ckt
from make_netlist import make_netlist
from my_utils import get_COMPONENTS
from my_utils import reduce_nodes
from get_comp_class_bbox_orient import get_comp_bbox_class_orient

# get logger
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) #appending parent folder to sys path so that modules can be imported from there
from logger import get_logger
logger = get_logger(__name__)




# * GLOBAL VARIABLES
NON_ELECTRICAL_COMPS = [-1, -2] #classes for COMPONENTS like crossover, junction etc


def process_and_show_node_map(node_map: np.ndarray, ckt_img: Image.Image):
    """
    Processes a 2D numpy array by replacing NaN with 0,
    assigns a specific color to non-negative values,
    applies a dilation kernel to make nodes fatter,
    overlays the node map on the circuit image,
    and displays the result as a combined image.

    Parameters:
        node_map (numpy.ndarray): Input 2D numpy array.
        ckt_img (PIL.Image.Image): Circuit image to overlay the node map onto.

    Returns:

    """

    # Create a copy to avoid modifying the original array
    processed_map = np.nan_to_num(node_map, nan=-1)  # Replace NaN with -1

    # Create an RGB map
    height, width = processed_map.shape
    colored_map = np.zeros((height, width, 3), dtype=np.uint8)

    # Assign green color to non-negative values
    non_negative_mask = processed_map >= 0  # Non-negative values
    dilation_kernel_size = 5
    dilated_mask = binary_dilation(non_negative_mask, structure=np.ones((dilation_kernel_size, dilation_kernel_size)))  # Apply dilation
    colored_map[dilated_mask] = (0, 255, 0)  # Green for non-negative values

    # Convert to a PIL image
    node_map_img = Image.fromarray(colored_map)

    # Annotate node names
    draw = ImageDraw.Draw(node_map_img)
    try:
        font = ImageFont.truetype("arial.ttf", size=50)  # Load a font
    except IOError:
        font = ImageFont.load_default()  # Fallback to default font if "arial.ttf" is not found

    unique_values = np.unique(processed_map)
    for value in unique_values:
        if value >= 0:
            y, x = np.argwhere(processed_map == value)[0]  # Get the first occurrence of the node
            draw.text((x+2, y+2), str(int(value)), fill="white", font=font)

    # Resize the node map to match the circuit image size
    node_map_img_resized = node_map_img.resize(ckt_img.size, resample=Image.BILINEAR)

    # Combine the two images
    combined_img = ckt_img.convert("RGBA").copy()
    node_map_img_resized = node_map_img_resized.convert("RGBA")

    # Blend the images (node map overlay is semi-transparent)
    combined_img = Image.blend(combined_img, node_map_img_resized, alpha=0.3)

    return combined_img 



def img2nl(path: str):
    '''
    given the path to an image, it returns ??
    '''
    global NON_ELECTRICAL_COMPS
    ekdom_start = time.time()

    start_time = time.time()  # Record the start time

    ckt_img = Image.open(path).convert('L')  # Convert to grayscale
    end_time = time.time()  # Record the end time

    # * skeletonize the ckt
    start_time = time.time()  # Record the start time

    ckt_img_enhanced = img_preprocess(ckt_img, contrast_factor=1, sharpness_factor=1, show_enhanced_img=False)
    skeleton_ckt = skeletonize_ckt(ckt_img_enhanced, kernel_size=6,show_skeleton_ckt=False)
    ############################################################################################
    
    end_time = time.time()  # Record the end time
    logger.info(f"Execution time for skeletonize : {end_time - start_time:.4f} seconds")

    # * get component bounding box
    start_time = time.time()  # Record the start time
    comp_bbox = get_comp_bbox_class_orient(path)

    end_time = time.time()  # Record the end time
    logger.info(f"Execution time for all models: {end_time - start_time:.4f} seconds")

    ## only keeping the electrical COMPONENTS in the ckt skeleton image
    # electrical_component_bbox = [[comp_class, x, y, w, h, comp_orientation, comp_name], [....], .....] 
    electrical_component_bbox = comp_bbox.copy()

    for index, row in enumerate(electrical_component_bbox):
        if row[0] in NON_ELECTRICAL_COMPS:
            electrical_component_bbox[index] = None

    electrical_component_bbox = [x for x in electrical_component_bbox if x!=None]
    


    # * assigning nodes to components
    start_time = time.time()  # Record the start time

    COMPONENTS, NODE_MAP, all_start_points = get_COMPONENTS(skeleton_ckt, comp_bbox)


    # * finding connection between components and reducing node counts
    reduce_nodes(skeleton_ckt, comp_bbox, NODE_MAP, COMPONENTS, all_start_points)
    
    end_time = time.time()  # Record the end time
    logger.info(f"Execution time for nodal algos: {end_time - start_time:.4f} seconds")

    # * make ckt netlist
    start_time = time.time()  # Record the start time

    circuit = make_netlist(COMPONENTS) # from the connection described in the COMPONENTS array, get the circuit object
    ckt_netlist_str = str(circuit)


    ekdom_sesh = time.time()
    logger.info(f"total execution time: {ekdom_sesh - ekdom_start:.4f} seconds")

    combined_img = process_and_show_node_map(NODE_MAP, ckt_img)

    return ckt_netlist_str, combined_img


if __name__ == "__main__":
    # path = r"ckt5.jpg"
    # path = r"C:\Users\Touhid2\Desktop\50_jpg.rf.dfa9222529f42fb211b7fd65119dddf3.jpg"
    # path = r"ckt1.jpeg"

    # path = r"val_data/ckt10.jpg"
    path = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\val_data\motu_challenge_ckt.jpeg"
    netlist, combined_img = img2nl(path)
    print(f"netlist: {netlist}")
    
    # Display the combined image
    combined_img.show()


