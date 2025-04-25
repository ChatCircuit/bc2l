import logging, os
from dotenv import load_dotenv
load_dotenv()


def get_logger(name=__name__):
    logger = logging.getLogger(name)
    
    #################################
    ##### SET LOGGER LEVEL HERE 
    logger.setLevel(os.getenv("LOGGING_LEVEL", "INFO"))
    #################################


    if not logger.handlers:
        ch = logging.StreamHandler() # console handler
        ch.setLevel(logging.DEBUG) # console handler level filter
        
        ###################################
        #### SET LOGGER FORMAT HERE 
        formatter = logging.Formatter('\t[%(levelname)s] %(name)s: %(message)s\n')
        ###################################
        
        
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger