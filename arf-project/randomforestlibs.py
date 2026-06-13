import math
import sklearn as skl
import sklearn.tree as tree
import sklearn.ensemble as ensemble
import sklearn.metrics as sklm
import sklearn.naive_bayes as nb
import sklearn.multiclass as sklmu
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
import copy


diabetes = pd.read_csv("Lab8DecisionTrees/diabetes.csv")
for attribute in diabetes:
    if attribute == '\'class\'': continue
    diabetes[attribute] = diabetes[attribute].astype(int)
print(diabetes)

train, test = train_test_split(diabetes, test_size=0.33, random_state=1, stratify=diabetes['\'class\''])

train.to_csv("Lab8DecisionTrees/forest-libs-train.csv")
test.to_csv("Lab8DecisionTrees/forest-libs-test.csv")

print(train)

diabetes.loc[diabetes['\'class\''] == 'tested_positive', '\'class\''] = 1
diabetes.loc[diabetes['\'class\''] == 'tested_negative', '\'class\''] = 0
y = diabetes['\'class\'']
y = np.ravel(y)
y=y.astype('float')
X = diabetes.drop('\'class\'', axis=1)
X = np.array(X).astype(int)
y = np.array(y).astype(int)
X_train, X_test = train_test_split(X, test_size=0.33, random_state=1, stratify=y)
y_train, y_test = train_test_split(y, test_size=0.33, random_state=1, stratify=y)

model = ensemble.RandomForestClassifier()
model.fit(X_train, y_train)
predictions = model.predict(X_test)
accuracy = sklm.accuracy_score(y_test, predictions)

y_t = y_test
y_test = predictions

print(model)
print(predictions)
print("accuracy:", accuracy)
print("prec", sklm.precision_score(y_t, y_test))
print("rec or sens", sklm.recall_score(y_t, y_test))
print("spec", sklm.recall_score(y_t, y_test, pos_label=0))
print("f_measure", sklm.f1_score(y_t, y_test))
print("mcc", sklm.matthews_corrcoef(y_t, y_test))