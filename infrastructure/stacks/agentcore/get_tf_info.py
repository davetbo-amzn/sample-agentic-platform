import json

class GetTfInfo:
    def __init__(self):
        with open('../../infrastructure/stacks/agentcore/terraform.tfstate', 'r') as vars_in:
            self.outputs = json.loads(vars_in.read())['outputs']
    
    def get_tf_info(self, keys=[]):
        results = {}
        for key in self.outputs.keys():
            if len(keys) == 0 or \
                len(keys) > 0 and key in keys:
                results[key] = self.outputs[key]
        return results

        
        

        

