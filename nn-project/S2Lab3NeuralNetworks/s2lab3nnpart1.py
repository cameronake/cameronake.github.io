import math
import random

# which activation function to use
transformation = "T3"

# series of hyperparameters I used to make sure the neural network doesn't end up with exploding gradient or too much time or so forth
CUTOFF = 100 #number of repetitions to cut off after if total error does not go below 0.01
ERRORDIFF = 0.001
ERRORDIFFIMPLEMENTFIRST = 18 #first repetition to implement "if totalloss - oldloss <= ERRORDIFF restart"
HIGHERROR = 5000 #lowest error to implement "if totalloss > HIGHERROR restart"
ERRORTOIMPLEMENTGRADS = 0.05 #lowest error to implement "if sum_grads > MINSUMGRADS restart"

NUMTRAINING = 50 #number of points in uniform training set on EACH AXIS, x and y from -1.5 to 1.5 - sqrt of total number of training points you want
MAXWIDTH = 1.5

t_funcs = {"T1": lambda x: x, 
          "T2": lambda x: x if x>0 else 0,
          "T3": lambda x: 0 if x<-500 else 1/(1+math.exp(-x)),
          "T4": lambda x: (2/(1+math.exp(-x)))+1}

derivs = {"T1": lambda y: 1,
          "T2": lambda y: 1 if y>0 else 0,
          "T3": lambda y: y*(1-y),
          "T4": lambda y: (1-y*y)/2}

sign_functions = {">=": lambda x, y: x >= y,
                 "<=": lambda x, y: x <= y,
                 ">": lambda x, y: x > y,
                 "<": lambda x, y: x < y}

indata = [] #one line for each piece of input data; last value in each line is output value

'''
x = -MAXWIDTH
y = -MAXWIDTH
inc = 2 * MAXWIDTH / NUMTRAINING

while y <= MAXWIDTH:
    while x <= MAXWIDTH:
        val = x*x + y*y
        indata.append([x, y, 1, [0, 1][sign_functions[sign](val, radius)]])
        x += inc
    y += inc
    x = -MAXWIDTH

NUMGENERATED = 30000
DIST = 0.3
for c in range(NUMGENERATED):
    rad = 0
    while rad > radius + 0.2 or rad < radius - 0.2:
        x = random.random() * 3 - 1.5
        y = random.random() * 3 - 1.5
        rad = x*x+y*y
    val = [0, 1][sign_functions[sign](x*x + y*y, radius)]
    indata.append([x, y, 1, val])
'''

indata.append([.05, .10, [.01, .99]])

#recommended


#including input/output
layer_counts = [2, 2, 2]
#layer_counts = [3, 18, 8, 4, 1]
#weights_per_layer = [54, 144, 32, 4, 1]  #layer counts [3 to start, 18, 8, 4, 1, 1 to output]
#weights_per_layer = [90, 300, 10, 1] #layer counts [3 to start, 30, 10, 1, 1 to output]
weights_per_layer = [ct1 * ct2 for ct1, ct2 in zip(layer_counts[:-1], layer_counts[1:])]

# initialize laylists with all weights - random float between [-0.5, 0.5) - couldn't figure out how to make upper bound inclusive
laylists = [[random.random() * 4 - 2 for i in range(numweights)] for numweights in weights_per_layer] 
laylists = [[.15, .20, .25, .30], [.40, .45, .50, .55]]
print(laylists)

output_file = open("S2Lab3NeuralNetworks/output.txt", "w")

outmats = [] # matrices outputted through parsing - each row in matrix is the weight in the output layer; each column is the one coming out of the prior layer
for i in range(len(laylists) - 1, -1, -1): # store laylists as matrices instead of lists because ORGANIZATION
    laylist = laylists[i]
    mat = []
    if outmats == []:
        mat_height = layer_counts[-1]
    else: mat_height = len(outmats[0][0])
    mat_width = len(laylist) // mat_height
    for j in range(mat_height):
        mat += [laylist[(j * mat_width):((j + 1) * mat_width)]]
    outmats = [mat] + outmats
print(outmats)

#biases = [[random.random() * 4 - 2 for _ in range(layer_counts[i])] for i in range(len(layer_counts) - 1)]
biases = [[.35, .35], [.60, .60]]
print(biases)

def reinitialize_outmats(weights_per_layer):
    # initialize laylists with all weights - random float between [-2.0, 2.0) - couldn't figure out how to make upper bound inclusive
    laylists = [[random.random() * 4 - 2 for i in range(numweights)] for numweights in weights_per_layer] 
    #laylists = [[0.5 for i in range(numweights)] for numweights in weights_per_layer]
    outmats = [] # matrices outputted through parsing - each row in matrix is the weight in the output layer; each column is the one coming out of the prior layer
    for i in range(len(laylists) - 1, -1, -1): # store laylists as matrices instead of lists because ORGANIZATION
        laylist = laylists[i]
        mat = []
        if outmats == []:
            mat_height = layer_counts[-1]
        else: mat_height = len(outmats[0][0])
        mat_width = len(laylist) // mat_height
        for j in range(mat_height):
            mat += [laylist[(j * mat_width):((j + 1) * mat_width)]]
        outmats = [mat] + outmats
    return outmats

def transpose(matrix):
    return [[matrix[i][j] for i in range(len(matrix))] for j in range(len(matrix[0]))]

def transfer(t_funct, input):
    return t_funcs[t_funct](input)

def dot_product(input, weights):
    prod = 0
    for i in range(len(input)):
        prod += input[i] * weights[i]
    return prod

def evaluate(outmats, biases, input_vals, t_funct):
    line = input_vals
    node_vals = [line]
    for matrix, bias_list in zip(outmats, biases):
        outs = []
        for weights, bias in zip(matrix, bias_list):
            y = dot_product(line, weights) + bias
            out = transfer(t_funct, y)
            outs.append(out)
        line = outs
        node_vals.append(line)
        #print(node_vals)
    return node_vals

def error_of_output(actual, output):
    return sum(((a_val - o_val)**2)/2 for a_val, o_val in zip(actual, output))

def eval_and_find_errorlist(outmats, biases, input_vals_lists, expected_outputs_lists, transformation):
    node_vals_lists = []
    vals_to_calc_loss = []
    exp_and_output = [] #list of tuples for each training example of (expected, output)
    for input_vals, expected_vals in zip(input_vals_lists, expected_outputs_lists):
        node_vals = evaluate(outmats, biases, input_vals, transformation)
        output_vals = node_vals[len(node_vals) - 1]
        vals_to_calc_loss.append(error_of_output(expected_vals, output_vals))
        exp_and_output.append((expected_vals, output_vals))
        node_vals_lists.append(node_vals)
    return vals_to_calc_loss, node_vals_lists, exp_and_output

def find_gradient_matrices(outmats, biases, t_funct, total_loss, node_vals, exp_and_output):
    #print()
    #print("THIS FUNCTION WAS CALLED")
    #print()
    #print("outmats", outmats)
    #print("node vals", node_vals)
    #if random.randint(1, 100) == 100: print("exp_and_output", exp_and_output)
    layer = len(node_vals) - 1
    gradients = []
    bias_gradients = []
    #print(node_vals)
    most_recent_errors = [exp - output for exp, output in zip(exp_and_output[0], exp_and_output[1])]
    #print(most_recent_errors)
    '''
    if random.random() > 0.995: 
        print("exp_and_output", exp_and_output)
        print("last errors sum", sum(most_recent_errors))
        for l in node_vals:
            print("layer", l)
    '''
    #print("final weights", finalweights)
    #print("final grads", finalgrads)
    while layer >= 1:
        # use this to find actual errors by multiplying error values of later layers' nodes
        #print("outmats", outmats[layer], "transposed", transpose(outmats[layer]), "node_vals", node_vals[layer])
        errors_at_nodes = []
        for node in range(len(node_vals[layer])):
            d = derivs[t_funct](node_vals[layer][node])
            if layer == len(node_vals) - 1: error_at_node = d * most_recent_errors[node]
            else: 
                most_recent_grads = transpose(gradients[0]) #each row: coming out of input node
                error_at_node = d * sum(most_recent_grads[node]) # d * sum(most_recent_errors[i] for i in range(len(node_vals[layer+1])))
            #print("at node", error_at_node)
            errors_at_nodes.append(error_at_node)
        #print("for layer", layer)
        #print("most_recent_errors", most_recent_errors)
        #print("errors_at_nodes", errors_at_nodes)
        #print()
        g = []
        bias_g = []
        for node_error in errors_at_nodes:
            x_vals = node_vals[layer - 1]
            #print("node error", node_error, "x_list", x_vals)
            grad_list = [x * node_error for x in x_vals]
            g.append(grad_list)
            bias_g.append(node_error)
        #print(g)
        gradients = [g] + gradients
        bias_gradients = [bias_g] + bias_gradients
        most_recent_errors = errors_at_nodes
        layer -= 1
    #print("gradients", gradients)
    #print("bias grads", bias_gradients)
    #exit(1)
    return gradients, bias_gradients

def update_with_gradients(outmats, biases, all_gradients, bias_gradients, alpha=0.01):
    newoverall = outmats
    newbiases = biases
    '''
    print()
    print("all_gradients[0]", all_gradients[0])
    print()
    print("newoverall", newoverall)
    print()
    '''
    for gradients in all_gradients:
        newoverall = [[[weight + alpha * grad for weight, grad in zip(weights, grads)] 
                    for weights, grads in zip(layerweights, layergrads)]
                    for layerweights, layergrads in zip(newoverall, gradients)]
    for bias_gs in bias_gradients:
        newbiases = [[bias + alpha * grad for bias, grad in zip(bias_list, grads)]
                     for bias_list, grads in zip(biases, bias_gradients)]
    #print(newfinal)
    
    return newoverall, newbiases

def iterate(input_vals_lists, expected_outputs_lists, weights, biases, transformation):
    #print()
    #print(weights)
    #print(output_layer_weights)
    #print()
    vals_for_loss, node_vals_lists, exp_and_output = eval_and_find_errorlist(weights, biases,
                                                input_vals_lists,
                                                expected_outputs_lists,
                                                transformation)
    totalloss = sum(vals_for_loss)
    output_file.write("w1\tErrortotal")
    oldloss = 1000000
    num_iterations = 0
    most_recently_stopped = 0
    while totalloss >= 0.01: #and num_iterations < CUTOFF:
        if num_iterations % 4000 == 0:
            output_file.write("\n" + str(weights[0][0][0]) + "\t" + str(totalloss))
            #print(vals_for_loss)
        for ex_index in range(len(input_vals_lists)):
            all_examples_gradients = []
            vals_for_loss, node_vals_lists, exp_and_output = eval_and_find_errorlist(weights, biases,
                                                [input_vals_lists[ex_index]],
                                                [expected_outputs_lists[ex_index]],
                                                transformation)
            gradients, bias_grads = find_gradient_matrices(weights, biases,
                                            transformation,
                                            totalloss,
                                            node_vals_lists[0],
                                            exp_and_output[0])
            #print("grads", gradients)
            #print("bias grads", bias_grads)
            all_examples_gradients.append(gradients)
            #print()
            #print()
            #print("TOTAL LOSS", totalloss)
            '''
            if totalloss > 10000:
                formattedweights = []
                for layer_weights in weights:
                    layerweights = []
                    for node_weights in layer_weights:
                        layerweights += node_weights
                    formattedweights.append(layerweights)
                layer_counts = [len(weights[0][0])] + [len(weights[i]) for i in range(len(weights))] + [len(output_layer_weights)]
                print("Errors:", vals_for_loss)
                print()
                print("all_examples_gradients[0]", all_examples_gradients[0])
                print(all_examples_output_gradients[0])
                print()
                print("layerCts:", layer_counts)
                print("Weights:")
                for li in formattedweights:
                    print(li)
                print()
                print("output_layer_weights", output_layer_weights)
                print()
                break
            '''
            weights, biases = update_with_gradients(weights, biases,
                                            all_examples_gradients, bias_grads,
                                            alpha=(0.1 * (t_funcs["T3"](totalloss/len(expected_outputs_lists[0])) - 0.5)))
                                            #alpha=0.3)
        if num_iterations % 5 == 0: 
            formattedweights = []
            for layer_weights in weights:
                layerweights = []
                for node_weights in layer_weights:
                    layerweights += node_weights
                formattedweights.append(layerweights)
            layer_counts = [len(weights[0][0])] + [len(weights[i]) for i in range(len(weights))]
            #print("Errors:", vals_for_loss)
            '''
            print()
            print("all_examples_gradients[0]", all_examples_gradients[0])
            print()'''
            #print("layerCts:", layer_counts)
            #print("Weights:")
            #for li in formattedweights:
                #print(li)
        '''if totalloss - oldloss <= ERRORDIFF and num_iterations - most_recently_stopped >= ERRORDIFFIMPLEMENTFIRST:
            weights = reinitialize_outmats(weights_per_layer)
        if totalloss >= HIGHERROR:
            weights = reinitialize_outmats(weights_per_layer)
            '''
        vals_for_loss, node_vals_lists, exp_and_output = eval_and_find_errorlist(weights, biases,
                                                input_vals_lists,
                                                expected_outputs_lists,
                                                transformation)
        oldloss = totalloss
        totalloss = sum(vals_for_loss)
        num_iterations += 1
    return weights, biases, vals_for_loss
    
print(indata)

input_vals_lists = [point[:len(point)-1] for point in indata]
expected_outputs_lists = [point[len(point)-1] for point in indata]
print(input_vals_lists)
print(expected_outputs_lists)
weights, biases, error_vals = iterate(input_vals_lists,
                                expected_outputs_lists,
                                outmats,
                                biases,
                                "T3")

formattedweights = []
for layer_weights in weights:
    layerweights = []
    for node_weights in layer_weights:
        layerweights += node_weights
    formattedweights.append(layerweights)

layer_counts = [len(weights[0][0])] + [len(weights[i]) for i in range(len(weights))]

#print("Errors:", error_vals)
print("layerCts:", layer_counts)
print("Weights:")
for li in formattedweights:
    print(li)


h, vals, eao = eval_and_find_errorlist(weights, biases, input_vals_lists, expected_outputs_lists, "T3")
print("Predicted:", vals, eao)