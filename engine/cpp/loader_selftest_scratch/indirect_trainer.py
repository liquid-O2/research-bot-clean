import torch
def build(tape):
    labels = tape.truth(['stop_hit'])
    for name, array in labels.items():
        stacked = torch.cat([array, array])
    return stacked
