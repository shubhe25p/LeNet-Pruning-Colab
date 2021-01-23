# LeNet-Pruning-Colab
Deep compression, a three stage pipeline: pruning, trained quantization and Huffman coding, that work together to reduce the storage requirement of neural networks by 35× to 49× without affecting their accuracy.

# Introduction
Deep Learning is successful because it has been able to perform better on wide variety of tasks which its increasing depth. This causes many-fold increment in its model parameters which will increase model size. Larger models take more memory which makes them harder to distribute especially in mobile devices . Larger models also take more time to run and can require more expensive hardware. This is especially a concern if you are deploying a model for a real-world application. Though these Deep Learning models are much powerful yet there weights are considerably large and consumes memory bandwidth. For example ALexnet is over 200Mb and VGG16 is over 500Mb. This huge model size prevent developers from implementing this state-of-the-art model on embedded devices. Additionally these model consumes a lot of power which is a huge disadvantage in mobile devices. 

# Previous Work
There exist many model pruning techniques out of which Lottery ticket hypothesis is the most common. All pruning methods has its own advantages and disadvantages. I started reading research papers to get a better understanding. Network pruning has been used both to reduce network complexity and to reduce over-fitting. An early approach to pruning was biased weight decay (Hanson & Pratt, 1989). Optimal Brain Damage (LeCun et al., 1989). A recent work (Han et al., 2015) successfully pruned several state of the art large scale networks and showed that the number of parameters could be reduce by an order of magnitude. There have attempts to train a pruning agent to produce a weight filter, every time it takes a pruning action, the action is evaluated by a reward function(Huang et al., 2018). I have implemented Deep Compression(ICLR 2016) which uses a three stage pipeline to reduce the model size by 35x to 49x without affecting their accuracy.

# First Stage of the Pipeline
The first stage prunes the network weights where we can do this by setting individual parameters to zero and making the network sparse or prune weight values with near zero or negative values. This would lower the number of parameters in the model while keeping the architecture the same. Learning the right connections is an iterative process. Pruning followed by a retraining is one iteration, after many such iterations the minimum number connections could be found. This reduces the number of weights by 9x to 13x. I trained LeNet-300-100 model with MNIST data that pruned weights with very low value.

# Second Stage of the Pipeline
The second stage is quantization and weight sharing which further reduces the size of the network. It reduces the number of bits required to represent each weight. The weight sharing is proven to reduce the size of network by many folds. It groups similar weights and by the method of K-Means clustering from sklearn library. The compression rate is described by an equation which is described in the paper. This stage combined with the previous stage is shown to have reduce the network size by approximately 27x to 31x.

# Third stage of the pipeline
The third stage is huffman coding which is a type of optimal prefix code used for lossless data compression. It consists of two parts: building the huffman tree and traversing it to give codes to characters. The encoding of weights and index is performed in a similar way. The final message consists of two parts: first encoded weights and indices and second describes the huffman tree which can be used for decoding.

# Conclusion
To conclude, the above algorithm was successful in reducing the size of the implemented LeNet 300-100 model from ~1070KB to ~27KB( 40X compression rate). This has been implemented successfully in Google Colab with Pytorch. The python notebook and script has the same code. Some parts of the code like huffman coding was understood intuitively and then taken from a git repository.

