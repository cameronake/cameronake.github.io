import math
import sklearn as skl
import sklearn.metrics as sklm
import sklearn.naive_bayes as nb
import sklearn.multiclass as sklmu
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
import copy
import random


diabetes = pd.read_csv("Lab8DecisionTrees/diabetes.csv")
for attribute in diabetes:
    if attribute == '\'class\'': continue
    diabetes[attribute] = diabetes[attribute].astype(int)
print(diabetes)

def info(class_dist): #class_dist is an array with the number of instances in each class
    s = sum(class_dist)
    i = 0
    for c in class_dist:
        if c != 0: # just 0 if c is 0 and c = 0 messes up calculations
            i += -1 * c / s * math.log2(c / s) 
    return i

def gain_ratio_for_attribute(data, attribute): #data is a dataframe
    
    class_vals = data['\'class\'']
    class_l = list(class_vals)
    class_s = set(class_l)
    class_di = [class_l.count(c_v) for c_v in class_s]
    info_gain = info(class_di) # start with the original info, then subtract incrementally for each attribute val

    column = data[attribute]

    # calculate info_gain
    for val in set(column):

        # so mask doesn't get grumpy about index
        new_col = pd.Series(list(column))

        mask = list(new_col == pd.Series([val] * len(column)))
        class_values_for_this_val = data['\'class\''].loc[mask] # find class values for this value of this attribute
        
        class_vals_l = list(class_values_for_this_val)
        class_vals_s = set(class_vals_l)
        class_distribution = [class_vals_l.count(c_v) for c_v in class_vals_s]

        info_for_val = info(class_distribution)
        #print("proportion with val", val, len(class_vals_l) / len(mask))
        info_gain -= len(class_vals_l) / len(mask) * info_for_val # info * proportion of values

    # calculate split_info
    vals_l = list(column)
    vals_s = set(column)
    distribution = [vals_l.count(v) for v in vals_s]
    split_info = info(distribution)

    if split_info == 0: return 0.0  # so it doesn't give errors when it's all the same value

    # return gain_ratio
    return info_gain / split_info

def partition(data):

    max_gain_ratio = 0
    split_attribute = ''

    for attribute in data:
        if attribute == '\'class\'' or attribute == 'id' or attribute == '': continue
        ratio = gain_ratio_for_attribute(data, attribute)
        if ratio > max_gain_ratio:
            max_gain_ratio = ratio
            split_attribute = attribute
    
    column = data[split_attribute]
    split_data = [] #list of dataframes
    split_vals = [] #list of the attribute value for each split result

    for val in set(column):
        new_col = pd.Series(list(column))

        mask = list(new_col == pd.Series([val] * len(column)))
        data_for_this_val = data.loc[mask] # find data values for this value of this attribute
        split_data.append(data_for_this_val)
        split_vals.append(val)

    return split_data, split_attribute, split_vals

def make_tree(data): # partition data recursively, building dictionary-of-dictionaries along the way
    
    class_vals = data['\'class\'']
    class_l = list(class_vals)
    class_s = set(class_l)
    if len(class_s) == 1:
        return {'DONE': class_s.pop()} #if 'DONE' in dict, return dict['DONE']
    else:
        tree = {}

        split_data, split_attribute, split_vals = partition(data)
        for data, val in zip(split_data, split_vals):
            tree[(split_attribute, val)] = make_tree(data)
        
        return tree
    
def predict_from_tree(instance, tree): # tree is a dictionary; instance is a dataframe of one instance

    if 'DONE' in tree:
        return tree['DONE']
    else:
        # get split attribute
        split_attribute = ''
        for i in tree:
            split_attribute = i[0]
            break

        val = instance[split_attribute]

        if (split_attribute, val) not in tree:
            for v in set(diabetes[split_attribute]):
                if (split_attribute, v) in tree:
                    return predict_from_tree(instance, tree[(split_attribute, v)])
            # there should be no possibilities for split_attribute to not have any values in the tree

        # predict recursively
        return predict_from_tree(instance, tree[(split_attribute, val)])

def get_predicted_vals(data, tree): #data is a dataframe; returns predictions as list

    new_data = copy.deepcopy(data)
    new_data = new_data.reset_index()

    preds = []

    for i in new_data.index:
        instance = new_data.loc[i]
        pred = predict_from_tree(instance, tree)
        #instance['Prediction'] = pred
        preds.append(pred)

    return preds, new_data

def random_forest(train, test, num_trees=10): #TODO: this is being grumpy

    datas = []

    for _ in range(num_trees):
        new_data = copy.deepcopy(test)

        # mess with the data (sample it and drop a couple attributes)
        train_data = copy.deepcopy(train)
        train_data = train_data.sample(n=len(train_data) // 2, replace=True, axis=0, random_state=np.random.RandomState())

        tree = make_tree(train_data)
        preds = get_predicted_vals(new_data, tree)
        datas.append(new_data)
        preds = preds[0]
        new_data['pred'] = preds
        #print(new_data)
        #print()

    # find most common prediction

    finalpreds = []

    #find most common prediction for each index
    for i in test.index:

        pos_count = 0
        neg_count = 0
        for pred_data in datas:
            if i in pred_data.index:
                instance = pred_data.loc[i]
                if instance['pred'] == 'tested_positive': pos_count += 1
                else: neg_count += 1
        if pos_count > neg_count: finalpreds.append('tested_positive')
        else: finalpreds.append('tested_negative')

    new_test = copy.deepcopy(test)
    new_test['prediction'] = finalpreds
    print("\n\nTEST DATA")
    print(new_test)
    return new_test
        




train, test = train_test_split(diabetes, test_size=0.33, random_state=1, stratify=diabetes['\'class\''])

train.to_csv("Lab8DecisionTrees/forest-manual-train.csv")
test.to_csv("Lab8DecisionTrees/forest-manual-test.csv")

test_data_with_predictions = random_forest(train, test, num_trees=101)

accuracy = list((pd.Series(test_data_with_predictions['prediction']) == test_data_with_predictions['\'class\''])).count(True) / len(test_data_with_predictions)

print("accuracy:", accuracy)
y_t = list(test_data_with_predictions['\'class\''])
y_test = list(test_data_with_predictions['prediction'])

print("prec", sklm.precision_score(y_t, y_test, pos_label='tested_positive'))
print("rec or sens", sklm.recall_score(y_t, y_test, pos_label='tested_positive'))
print("spec", sklm.recall_score(y_t, y_test, pos_label='tested_negative'))
print("f_measure", sklm.f1_score(y_t, y_test, pos_label='tested_positive'))
print("mcc", sklm.matthews_corrcoef(y_t, y_test))