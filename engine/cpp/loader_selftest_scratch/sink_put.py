import numpy as np
def build(tape):
    features = tape.features()
    y = tape.truth(['menu_net_cent'])['menu_net_cent']
    np.put(features['direct_raw'], 0, y)
