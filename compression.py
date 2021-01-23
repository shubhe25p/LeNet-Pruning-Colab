# -*- coding: utf-8 -*-
"""compression.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/14qhvcu5f0S2S9GI2vnfuc-xHaijJpa32
"""

import os
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from tqdm import tqdm
from torch.nn import Parameter
from torch.nn.modules.module import Module
import math
from sklearn.cluster import KMeans
from scipy.sparse import csc_matrix, csr_matrix
from collections import defaultdict, namedtuple
from heapq import heappush, heappop, heapify
import struct
from pathlib import Path
from scipy.sparse import csr_matrix, csc_matrix

args={
    "batch-size":50,
    "test-batch-size":1000,
    "epochs":100,
    "lr":0.01,
    "seed":42,
    "log-interval":10,
    "log":"log.txt",
    "sensitivity":2,
    "no_cuda":False
}
args["batch-size"]

torch.manual_seed(args["seed"])
use_cuda = not args["no_cuda"] and torch.cuda.is_available()
device = torch.device("cuda" if use_cuda else 'cpu')
if use_cuda:
    print("Yes CUDA!")
    torch.cuda.manual_seed(args["seed"])
else:
    print('No CUDA!!!')

from google.colab import drive
drive.mount('/content/gdrive')

import os
os.chdir('gdrive/My Drive/kaggle/self_compress') 
!ls

kwargs = {'num_workers': 5, 'pin_memory': True} if use_cuda else {}
train_loader = torch.utils.data.DataLoader(
    datasets.MNIST('data', train=True, download=True,
                   transform=transforms.Compose([
                       transforms.ToTensor(),
                       transforms.Normalize((0.1307,), (0.3081,))
                   ])),
    batch_size=args["batch-size"], shuffle=True, **kwargs)
test_loader = torch.utils.data.DataLoader(
    datasets.MNIST('data', train=False, transform=transforms.Compose([
                       transforms.ToTensor(),
                       transforms.Normalize((0.1307,), (0.3081,))
                   ])),
    batch_size=args["test-batch-size"], shuffle=False, **kwargs)

class PruningModule(Module):
    def prune_by_percentile(self, q=5.0, **kwargs):
        # Calculate percentile value
        alive_parameters = []
        for name, p in self.named_parameters():
            if 'bias' in name or 'mask' in name:
                continue
            tensor = p.data.cpu().numpy()
            alive = tensor[np.nonzero(tensor)] # flattened array of nonzero values
            alive_parameters.append(alive)

        all_alives = np.concatenate(alive_parameters)
        percentile_value = np.percentile(abs(all_alives), q)
        print(f'Pruning with threshold : {percentile_value}')

        for name, module in self.named_modules():
            if name in ['fc1', 'fc2', 'fc3']:
                module.prune(threshold=percentile_value)

    def prune_by_std(self, s=0.25):
        for name, module in self.named_modules():
            if name in ['fc1', 'fc2', 'fc3']:
                threshold = np.std(module.weight.data.cpu().numpy()) * s
                print(f'Pruning with threshold : {threshold} for layer {name}')
                module.prune(threshold)

class MaskeL(Module):
    def __init__(self, in_features, out_features, bias=True):
        super(MaskeL, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.weight = Parameter(torch.Tensor(out_features, in_features))
        self.mask = Parameter(torch.ones([out_features, in_features]), requires_grad=False)
        if bias:
            self.bias = Parameter(torch.Tensor(out_features))
        else:
            self.register_parameter('bias', None)
        self.reset_parameters()

    def reset_parameters(self):
        stdv = 1. / math.sqrt(self.weight.size(1))
        self.weight.data.uniform_(-stdv, stdv)
        if self.bias is not None:
            self.bias.data.uniform_(-stdv, stdv)

    def forward(self, input):
        return F.linear(input, self.weight * self.mask, self.bias)

    def __repr__(self):
        return self.__class__.__name__ + '(' \
            + 'in_features=' + str(self.in_features) \
            + ', out_features=' + str(self.out_features) \
            + ', bias=' + str(self.bias is not None) + ')'

    def prune(self, threshold):
        weight_dev = self.weight.device
        mask_dev = self.mask.device
        tensor = self.weight.data.cpu().numpy()
        mask = self.mask.data.cpu().numpy()
        new_mask = np.where(abs(tensor) < threshold, 0, mask)
        self.weight.data = torch.from_numpy(tensor * new_mask).to(weight_dev)
        self.mask.data = torch.from_numpy(new_mask).to(mask_dev)

class LeNet(PruningModule):
    def __init__(self, mask=False):
        super(LeNet, self).__init__()
        linear = MaskeL if mask else nn.Linear
        self.fc1 = linear(784, 300)
        self.fc2 = linear(300, 100)
        self.fc3 = linear(100, 10)

    def forward(self, x):
        x = x.view(-1, 784)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = F.log_softmax(self.fc3(x), dim=1)
        return x

model = LeNet(mask=True).to(device)
print(model)

optimizer = optim.Adam(model.parameters(), lr=args["lr"], weight_decay=0.0001)
initial_optimizer_state_dict = optimizer.state_dict()

def train(epochs):
    model.train()
    for epoch in range(epochs):
        pbar = tqdm(enumerate(train_loader), total=len(train_loader))
        for batch_idx, (data, target) in pbar:
            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            output = model(data)
            loss = F.nll_loss(output, target)
            loss.backward()

            for name, p in model.named_parameters():
                if 'mask' in name:
                    continue
                tensor = p.data.cpu().numpy()
                grad_data = p.grad.data.cpu().numpy()
                grad_data = np.where(tensor==0, 0, grad_data)
                p.grad.data = torch.from_numpy(grad_data).to(device)

            optimizer.step()
            if batch_idx % args["log-interval"] == 0:
                done = batch_idx * len(data)
                percentage = 100. * batch_idx / len(train_loader)
                pbar.set_description(f'Train Epoch: {epoch} Loss: {loss.item():.6f}')


def test():
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            test_loss += F.nll_loss(output, target, reduction='sum').item() # sum up batch loss
            pred = output.data.max(1, keepdim=True)[1] 
            correct += pred.eq(target.data.view_as(pred)).sum().item()

        test_loss /= len(test_loader.dataset)
        accuracy = 100. * correct / len(test_loader.dataset)
        print(f'Test : Average loss: {test_loss:.4f}, Accuracy: {correct}/{len(test_loader.dataset)} ({accuracy:.2f}%)')
    return accuracy

def log(filename, content):
    with open(filename, 'a') as f:
        content += "\n"
        f.write(content)

train(args["epochs"])
accuracy = test()
log(args["log"], f"initial_accuracy {accuracy}")

os.mkdir('saves')
torch.save(model, f"saves/initial_model.ptmodel")
print("--- With pruning ---")
model.prune_by_std(args["sensitivity"])
accuracy = test()
log(args["log"], f"accuracy_after_pruning {accuracy}")

print("--- Retraining ---")
optimizer.load_state_dict(initial_optimizer_state_dict) 
train(args["epochs"])
torch.save(model, f"saves/model_after_retraining.ptmodel")
accuracy = test()

log(args["log"], f"accuracy_after_retraining {accuracy}")
def test(model, use_cuda=True):
    kwargs = {'num_workers': 5, 'pin_memory': True} if use_cuda else {}
    device = torch.device("cuda" if use_cuda else 'cpu')
    test_loader = torch.utils.data.DataLoader(
    datasets.MNIST('data', train=False, transform=transforms.Compose([
                       transforms.ToTensor(),
                       transforms.Normalize((0.1307,), (0.3081,))
                   ])),
    batch_size=1000, shuffle=False, **kwargs)
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            test_loss += F.nll_loss(output, target, reduction='sum').item() # sum up batch loss
            pred = output.data.max(1, keepdim=True)[1] # get the index of the max log-probability
            correct += pred.eq(target.data.view_as(pred)).sum().item()

        test_loss /= len(test_loader.dataset)
        accuracy = 100. * correct / len(test_loader.dataset)
        print(f'Test set: Average loss: {test_loss:.4f}, Accuracy: {correct}/{len(test_loader.dataset)} ({accuracy:.2f}%)')
    return accuracy

#Weight sharing by KMeans Algorithm

def weight_sharing(model, bits=5):
  for module in model.children():
    dev = module.weight.device
    weight = module.weight.data.cpu().numpy()
    shape = weight.shape
    mat = csr_matrix(weight) if shape[0] < shape[1] else csc_matrix(weight)
    min_ = min(mat.data)
    max_ = max(mat.data)
    space = np.linspace(min_, max_, num=2**bits)
    kmeans = KMeans(n_clusters=len(space), init=space.reshape(-1,1), n_init=1, precompute_distances=True, algorithm="full")
    kmeans.fit(mat.data.reshape(-1,1))
    new_weight = kmeans.cluster_centers_[kmeans.labels_].reshape(-1)
    mat.data = new_weight
    module.weight.data = torch.from_numpy(mat.toarray()).to(dev)

!ls

model = torch.load("saves/model_after_retraining.ptmodel")

print('accuracy before weight sharing')
test(model, use_cuda)
weight_sharing(model)
print('accuacy after weight sharing')
test(model, use_cuda)
os.makedirs('saves', exist_ok=True)
torch.save(model, f"saves/model_after_weight_sharing.ptmodel")

model=torch.load("saves/model_after_weight_sharing.ptmodel")
from huffmancoding import huffman_encode_model
huffman_encode_model(model)

