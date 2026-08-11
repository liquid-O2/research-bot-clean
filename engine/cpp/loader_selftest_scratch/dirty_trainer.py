import numpy as np
def build(tape):
    features = tape.features()
    truth = tape.truth(['menu_net_cent'])
    y = truth['menu_net_cent']
    return np.concatenate([features['direct_raw'], y], axis=1)
