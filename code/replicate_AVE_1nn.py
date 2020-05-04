import utils
from os import path

import numpy as np
from scipy import stats, sparse
from scipy.spatial.distance import pdist, squareform

from sklearn.cluster import AgglomerativeClustering
from sklearn.linear_model import LogisticRegression
from tqdm import tqdm

from sklearn.metrics import average_precision_score

##Set a random seed to make it reproducible!
np.random.seed(utils.getSeed())


##The J&J benchmark used single-linkage clustering. 
#Wallach et. al later showed how model performance was related to bias. 
#Here we reproduce this using a set of train/test splits
#also using single-linkage clustering.

#load up data:
x, y = utils.load_feature_and_label_matrices(type='morgan')
##select a subset of columns of 'y' to use as a test matrix:
#this is the same each time thanks to setting the random.seed.
col_indices = np.random.choice(243, 10, replace=False)
x_, y_ = utils.get_subset(x, y, indices=col_indices)


#This will be used for clustering:
distance_matrix = utils.fast_dice(x_)



#These will be used to save all the data so we don't have to repeatedly run this script
targets = list() #store which target is analyzed (not used)
cutoffs = list() #store the cutoff value used (dice distance)

aves_before_trim = list()
aves_after_trim = list()
auroc_before_trim = list()
auroc_after_trim = list()
ap_before_trim = list()
ap_after_trim = list()
sizes_before_trim = list()
sizes_after_trim = list()
one_nn_before = list()
one_nn_after = list()


for _ in tqdm(range(400)):
    #choose a random target:
    idx = np.random.choice(y_.shape[1])

    #choose a random clustering cutoff and cluster:
    cutoff = stats.uniform(0.05, 0.425).rvs()
    clusterer = AgglomerativeClustering(n_clusters=None, distance_threshold=cutoff, linkage='single', affinity='precomputed')
    clusterer.fit(distance_matrix)

    clabels = np.unique(clusterer.labels_)
    pos_labels = np.unique(clusterer.labels_[y_[:,idx]==1])
    neg_labels = clabels[~np.isin(clabels, pos_labels)]
    if min(len(pos_labels), len(neg_labels))<2:
        #print('Not enough positive clusters to split')
        continue
    
    test_clusters, train_clusters = utils.split_clusters(pos_labels, neg_labels, 0.2, 0.2, shuffle=True)

    actives_test_idx, actives_train_idx, inactives_test_idx, inactives_train_idx = utils.get_four_matrices(y_,idx,clusterer,test_clusters,train_clusters)
    if min([actives_test_idx.shape[0], actives_train_idx.shape[0], inactives_test_idx.shape[0], inactives_train_idx.shape[0]])<20:        
        #print('Not enough ligands to train and test')
        continue
    ave= utils.calc_AVE_quick(distance_matrix, actives_train_idx, actives_test_idx,inactives_train_idx, inactives_test_idx)
    aves_before_trim.append(ave)
    sizes_before_trim.append([actives_train_idx.shape[0], actives_test_idx.shape[0], inactives_train_idx.shape[0], inactives_test_idx.shape[0]])

    #Now we will trim some nearest neighbours and by doing so, reduce AVE.
    #trim from the inactives/train matrix first:
    inactive_dmat = distance_matrix[inactives_test_idx]
    new_inactives_train_idx = utils.trim(inactive_dmat, 
                                       inactives_train_idx, 
                                       inactives_test_idx,
                                             fraction_to_trim=0.3)
    #then trim from the actives/train matrix:
    active_dmat = distance_matrix[actives_test_idx]
    new_actives_train_idx = utils.trim(active_dmat,
                                    actives_train_idx, 
                                    actives_test_idx,
                                       fraction_to_trim=0.3)

    #now calculate AVE with this new split:
    ave= utils.calc_AVE_quick(distance_matrix, new_actives_train_idx, actives_test_idx, new_inactives_train_idx, inactives_test_idx)
    aves_after_trim.append(ave)
    sizes_after_trim.append([new_actives_train_idx.shape[0], actives_test_idx.shape[0], new_inactives_train_idx.shape[0], inactives_test_idx.shape[0]])

    
    #evaluate a LogReg model using the original single-linkage split
    results = utils.evaluate_split(x_, y_, idx, actives_train_idx, actives_test_idx, inactives_train_idx, inactives_test_idx, auroc=True, ap=True)
    auroc_before_trim.append(results['auroc'])
    ap_before_trim.append(results['ap'])

    test_indices = list(actives_test_idx)+list(inactives_test_idx)
    train_indices = list(actives_train_idx)+list(inactives_train_idx)
    y_test = y_[:,idx][test_indices]
    y_train = y_[:,idx][train_indices]
    preds = y_train[distance_matrix[test_indices][:,train_indices].argmin(1)]
    one_nn_acc = average_precision_score(y_test, preds)
    one_nn_before.append(one_nn_acc)


    train_indices = list(new_actives_train_idx)+list(new_inactives_train_idx)
    y_train = y_[:,idx][train_indices]
    preds = y_train[distance_matrix[test_indices][:,train_indices].argmin(1)]
    one_nn_acc = average_precision_score(y_test, preds)
    one_nn_after.append(one_nn_acc)
    


    
    #evaluate a LogReg model using the new (lower AVE) split:
    results = utils.evaluate_split(x_, y_, idx, new_actives_train_idx, actives_test_idx, new_inactives_train_idx, inactives_test_idx, auroc=True, ap=True)
    auroc_after_trim.append(results['auroc'])
    ap_after_trim.append(results['ap'])
    
    cutoffs.append(cutoff)
    
    targets.append(idx)

    
##Save all the AVEs and model prediction data:
np.save('./processed_data/temp/aves_before_trim.npy', np.array(aves_before_trim))
np.save('./processed_data/temp/aves_after_trim.npy', np.array(aves_after_trim))
np.save('./processed_data/temp/auroc_before_trim.npy', np.array(auroc_before_trim))
np.save('./processed_data/temp/auroc_after_trim.npy', np.array(auroc_after_trim))
np.save('./processed_data/temp/ap_before_trim.npy', np.array(ap_before_trim))
np.save('./processed_data/temp/ap_after_trim.npy', np.array(ap_after_trim))
np.save('./processed_data/temp/sizes_before_trim.npy', np.array(sizes_before_trim))
np.save('./processed_data/temp/sizes_after_trim.npy', np.array(sizes_after_trim))
np.save('./processed_data/temp/targets.npy', np.array(targets))
np.save('./processed_data/temp/cutoffs.npy', np.array(cutoffs))

np.save('./processed_data/temp/one_nn_before.npy', np.array(one_nn_before))
np.save('./processed_data/temp/one_nn_after.npy', np.array(one_nn_after))