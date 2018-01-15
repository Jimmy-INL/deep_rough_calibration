import tensorflow as tf
from math import sqrt
from collections import namedtuple

def dense_relu(inputs, units, seed, name='dense_relu'):
    """
    Definition of a fully-connected layer with ReLU activations.

    Arguments:
    ----------
        inputs: tensor, shape=[None, dim_in].
            Features or previous layer as input to this dense layer.
        units: int.
            Number of units in this layer.
        seed: int.
            PRNG setting used for weight initializiation.
        name: string.
            Name of the layer (used for Tensorboard).

    Returns:
    --------
        dense_layer: tensor, shape=[None, units]
    """

    # Specify the number of units/features incoming.
    dim_in = inputs.get_shape().as_list()[1]

    with tf.name_scope(name):

        # Weight initialization optimized for ReLUs a la He et al. (2015).
        kernel_init= tf.truncated_normal_initializer(stddev=sqrt(2.0/dim_in), 
                                                     seed=seed)

        # Functional interface for dense layer.
        dense_layer = tf.layers.dense(inputs, units, 
                                      activation=tf.nn.relu, 
                                      kernel_initializer=kernel_init) 

        return dense_layer
                                            

def dense_relu_bn_drop(inputs, units, seed, training_phase, pkeep, 
                       name='dense_relu_bn_drop'):
    """
    Definition of a fully-connected layer with ReLU activations, droupout and
    batch normalization AFTER the activations.
    
    Arguments:
    ----------
        inputs: tensor, shape=[None, dim_in].
            Input features or previous layer as input to this layer.
        units: int.
            Number of units of this layer.
        seed: int.
            PRNG setting used for weight initializiation.
        training_phase: boolean.
            For batchnorm: If training, set True. If test, set False.
        pkeep: float, in (0,1).
            For dropout: Probability of keeping units during droupout.
        name: string.
            Name of the layer (used for Tensorboard).

    Returns:
    --------
        output: tensor, shape=[None, units].
            Output of layer run through dropout procedure.
    """

    with tf.name_scope(name):

        # Dense layer with ReLU activations.
        l1 = dense_relu(inputs, units, seed)

        # Applying batch normalisaton by Ioffe et al. (2015).
        l2 = tf.layers.batch_normalization(l1, center=True, scale=True,
                                           training=training_phase)

        # Applying dropout by Srivastava et al. (2014).
        output = tf.nn.dropout(l2, pkeep)

        return output


def dense_nn(nb_features, layer_sizes, nb_labels, seed):
    """
    Utility function that takes a specified NN topology (# units & layers)
    and returns a tensorflow computational graph of a fully connected (dense)
    neural network to be used for training and testing.

    Arguments:
    ----------
        nb_features: int.
            Number of features in labeled data.
        layer_sizes: array-like, shape=[, # layers].
            List with number of units per hidden layer, e.g. [32,16,8,4].
        nb_labels: int.
            Number of labels in labeled data.
        seed: int.
            PRNG setting used for weight initializiation.

    Returns:
    --------
        nn: named tuple.
            nn.inputs: tf.placeholder(tf.float32, [None, nb_features]).
                Tensorflow input placeholder for neural network.
            nn.labels: tf.placeholder(tf.float32, [None, nb_labels]).
                Tensorflow placeholder for labels.
            nn.pkeep: tf.placeholder(tf.float32).
                Regularisation via Dropout: Probability of keeping nodes.
            nn.predictions: tf op(tf.float32, [None, nb_labels]).
                Final/output layer of neural network.
            nn.loss: tf op (tf.float32)
                Loss op in computational graph computing loss function.
            nn.err_2pc: tf op (tf.float32)
                Percentage of predictions with relative error of more than 2%.
            nn.err_1pc: tf op (tf.float32)
                Percentage of predictions with relative error of more than 1%.

    """

    ## INITIALIZATION

    tf.reset_default_graph()

    # Creating a class of named tuples collecting neural network ops.
    NeuralNetwork = namedtuple('nn', 'inputs, labels, pkeep, training_phase, \
                                predictions, loss, err_2pc, err_1pc')

    # Placeholders for labeled pair of training data.
    inputs = tf.placeholder(tf.float32, [None, nb_features], name='inputs')
    labels = tf.placeholder(tf.float32, [None, nb_labels], name='labels')

    # Batchnorm (Ioffe et al. (2015)).
    training_phase = tf.placeholder(tf.bool, name='training_phase')

    # Dropout (Srivastava et al. (2014)): Probability of keeping nodes.
    pkeep = tf.placeholder(tf.float32, name='pkeep')

    ## CONSTRUCTION OF COMPUTATIONAL GRAPH OF FULLY CONNECTED NN

    nb_hidden_layers = len(layer_sizes)
    layers = []

    # Dealing with special case of first hidden layer.
    first_layer = dense_relu_bn_drop(inputs, layer_sizes[0], seed, 
                                   training_phase, pkeep, 'dense_hidden_0')

    layers.append(first_layer)

    # Dealing with hidden layers between first and final prediction layer.
    for i in range(nb_hidden_layers - 1):

        hidden_layer = dense_relu_bn_drop(layers[i], layer_sizes[i+1], seed,
                                          training_phase, pkeep,
                                          'dense_hidden_%s' % str(i+1))

        layers.append(hidden_layer)

    # Dealing with final prediction layer.
    prediction_layer = dense_relu(layers[-1], nb_labels, seed, 'predictions')

    ## ADDING LOSS & ACCURACY/ERROR TO COMPUTATIONAL GRAPH

    # Define the loss function.
    with tf.name_scope('loss'):
        loss = tf.reduce_mean(tf.square(prediction_layer-labels))
        tf.summary.scalar('loss', loss)

    # Define accuracy = % of predictions with RE < certain threshold.
    with tf.name_scope('accuracy'):

        # Define the relative error as a metric of accuracy for predictions.
        relative_error = tf.abs(prediction_layer-labels)/labels

        # Relative error less than 2%
        close_prediction_2pc = tf.greater(relative_error, 0.02)
        err_2pc = tf.reduce_mean(tf.cast(close_prediction_2pc, tf.float32))
        tf.summary.scalar('error_2pc', err_2pc)

        # Relative error less than 1%
        close_prediction_1pc = tf.greater(relative_error, 0.01)
        err_1pc = tf.reduce_mean(tf.cast(close_prediction_1pc, tf.float32))
        tf.summary.scalar('error_1pc', err_1pc)

    ## COLLECTION OPS AND INFOS OF NN IN NAMED TUPLE

    nn = NeuralNetwork(inputs = inputs,
                       labels = labels,
                       pkeep  = pkeep,
                       training_phase = training_phase,
                       predictions = prediction_layer,
                       loss = loss,
                       err_2pc = err_2pc,
                       err_1pc = err_1pc)

    return nn

    