# -*- coding: utf-8 -*-
"""digit-recognizer.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1yMC3ecdQsGEb9ynt1nNvu0ROYHrJ_Nku

# Digit Recognizer

## Mount Google Drive
"""

from google.colab import drive

drive.mount("/content/drive")

"""## Import libraries"""

# Commented out IPython magic to ensure Python compatibility.
import numpy as np  # linear algebra
import pandas as pd  # data processing, CSV file I/O (e.g. pd.read_csv)
import matplotlib.pyplot as plt

from PIL import Image
from sklearn.model_selection import train_test_split
import math
import copy
import time
import os

import torch
import torchvision
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torch.utils.data import DataLoader, TensorDataset
from torchvision.utils import make_grid

# neural net imports
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import Variable

# %matplotlib inline
print(torch.__version__)

random_seed = 42
torch.backends.cudnn.enabled = False
torch.manual_seed(random_seed)

# Load the data
base_path = "drive/MyDrive/kaggle/digit-recognizer"
train_df = pd.read_csv(os.path.join(base_path, "train.csv"))
test_df = pd.read_csv(os.path.join(base_path, "test.csv"))

y = train_df["label"]
x = train_df.drop("label", axis=1)

# Split training data into Train and validation set
X_train, X_valid, y_train, y_valid = train_test_split(
    x, y, test_size=0.15, shuffle=True
)

num_epoch = 50
batch_size_train = 32
batch_size_test = 32
learning_rate = 0.002
momentum = 0.9
log_interval = 100

train_df.head()

"""define Custom Dataset in order to do convert to tensor, do some transitions abd process data in mini-batches. Dataset takes two dataframe data.  
テンソルに変換し、トランジションを行い、ミニバッチでデータを処理するために、カスタムデータセットを定義する。データセットは2つのデータフレームを持つ。
"""


# CustomDatasetFromDF
class MNISTDataset(Dataset):
    def __init__(self, data, target, train=True, transform=None):
        """
        Args:
            csv_path (string): path to csv file
            transform: pytorch transforms for transforms and tensor conversion
        """
        self.train = train
        if self.train:
            self.data = data
            self.labels = np.asarray(target.iloc[:])
        else:
            self.data = data
            self.labels = None
        self.height = 28  # Height of image
        self.width = 28  # Width of image
        self.transform = transform

    def __getitem__(self, index):
        # Read each 784 pixels and reshape the 1D array ([784]) to 2D array ([28,28])
        img_as_np = (
            np.asarray(self.data.iloc[index][0:])
            .reshape(self.height, self.width)
            .astype("uint8")
        )
        # Convert image from numpy array to PIL image, mode 'L' is for grayscale
        img_as_img = Image.fromarray(img_as_np)
        img_as_img = img_as_img.convert("L")
        img_as_tensor = img_as_img

        if self.train:
            single_image_label = self.labels[index]
        else:
            single_image_label = None

        # Transform image to tensor
        if self.transform is not None:
            img_as_tensor = self.transform(img_as_img)

        if self.train:
            # Return image and the label
            return (img_as_tensor, single_image_label)
        else:
            return img_as_tensor

    def __len__(self):
        return len(self.data.index)


"""## Data normalization and Data augmentation
The values 0.1310 and 0.3085 used for the `Normalize()` transformation below are the global mean and standard deviation of the MNIST dataset. Following code is used to calculate mean/std dev of dataset. It take `dataloader` as input.  
以下の`Normalize()`で使用される値、0.1310と0.3085は、MNISTデータセットの全体平均と標準偏差。以下のコードはデータセットの平均と標準偏差を計算するために使用。`dataloader` を入力とする。  

`RandomRotation` at a specific degree (15 in our case below) that rotates some of them randomly at an angle of 15 degree again with a probability of p which defaults to 0.5.  
`RandomRotation`は、特定の角度(以下の例では15度)で、そのうちのいくつかを15度の角度でランダムに回転させる。
"""


def calculate_img_stats_full(dataset):
    imgs_ = torch.stack([img for img, _ in dataset], dim=1)
    imgs_ = imgs_.view(1, -1)
    imgs_mean = imgs_.mean(dim=1)
    imgs_std = imgs_.std(dim=1)
    return imgs_mean, imgs_std


transformations_org = transforms.Compose([transforms.ToTensor()])
train_org = MNISTDataset(x, y, True, transformations_org)

calculate_img_stats_full(train_org)

transformations_train = transforms.Compose(
    [
        transforms.RandomRotation(15),
        transforms.RandomAffine(0, shear=10, scale=(0.8, 1.2)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.1310], std=[0.3085]),
    ]
)


transformations_valid = transforms.Compose(
    [transforms.ToTensor(), transforms.Normalize(mean=[0.1310], std=[0.3085])]
)

train = MNISTDataset(X_train, y_train, True, transformations_train)
valid = MNISTDataset(X_valid, y_valid, True, transformations_valid)
test = MNISTDataset(
    data=test_df, target=None, train=False, transform=transformations_valid
)

"""Split the dataset with all transformations, augmentations and normalisation applied into TRAIN and VALIDATION to obtain the final DataLoaders.  
すべての変換、補強、正規化を適用したデータセットを、trainとvalidationに分割して、最終的なDataLoadersを取得。
"""

train_loader = DataLoader(
    train, batch_size=batch_size_train, num_workers=2, shuffle=True
)
valid_loader = DataLoader(
    valid, batch_size=batch_size_test, num_workers=2, shuffle=True
)
test_loader = DataLoader(test, batch_size=batch_size_test, shuffle=False)

"""## Building the Network"""


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv_block = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )

        self.linear_block = nn.Sequential(
            nn.Dropout(p=0.5),
            nn.Linear(128 * 7 * 7, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(64, 10),
        )

    def forward(self, x):
        x = self.conv_block(x)
        x = x.view(x.size(0), -1)
        x = self.linear_block(x)
        return x


"""## Training the Model"""


def train():
    criterion = nn.CrossEntropyLoss()

    if torch.cuda.is_available():
        cnn_model.cuda()
        criterion.cuda()

    optimizer = optim.Adam(params=cnn_model.parameters(), lr=learning_rate)
    exp_lr_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min")

    train_losses = []
    train_counter = []
    test_losses = []
    test_counter = [i * len(train_loader.dataset) for i in range(1, num_epoch + 1)]

    best_model_wts = copy.deepcopy(cnn_model.state_dict())
    best_acc = 0.0

    since = time.time()

    for epoch in range(1, num_epoch + 1):
        cnn_model.train()
        for i, (images, labels) in enumerate(train_loader):
            images = Variable(images).cuda()
            labels = Variable(labels).cuda()
            # Clear gradients
            optimizer.zero_grad()
            # Forward pass
            outputs = cnn_model(images)
            # Calculate loss
            loss = criterion(outputs, labels)
            # Backward pass
            loss.backward()
            # Update weights
            optimizer.step()
            if (i + 1) % log_interval == 0:
                print(
                    "Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}".format(
                        epoch,
                        (i + 1) * len(images),
                        len(train_loader.dataset),
                        100.0 * (i + 1) / len(train_loader),
                        loss.data,
                    )
                )
                train_losses.append(loss.item())
                train_counter.append(
                    (i * 64) + ((epoch - 1) * len(train_loader.dataset))
                )
        cnn_model.eval()
        loss = 0
        running_corrects = 0
        with torch.no_grad():
            for i, (data, target) in enumerate(valid_loader):
                data = Variable(data).cuda()
                target = Variable(target).cuda()
                output = cnn_model(data)
                loss += F.cross_entropy(output, target, reduction="sum").item()
                _, preds = torch.max(output, 1)
                running_corrects += torch.sum(preds == target.data)
        loss /= len(valid_loader.dataset)
        test_losses.append(loss)
        epoch_acc = 100.0 * running_corrects.double() / len(valid_loader.dataset)
        print(
            "\nAverage Val Loss: {:.4f}, Val Accuracy: {}/{} ({:.3f}%)\n".format(
                loss, running_corrects, len(valid_loader.dataset), epoch_acc
            )
        )
        if epoch_acc > best_acc:
            best_acc = epoch_acc
            best_model_wts = copy.deepcopy(cnn_model.state_dict())
        exp_lr_scheduler.step(loss)

    time_elapsed = time.time() - since
    print(
        "Training complete in {:.0f}m {:.0f}s".format(
            time_elapsed // 60, time_elapsed % 60
        )
    )
    print("Best val Acc: {:4f}".format(best_acc))

    return train_counter, train_losses, test_counter, test_losses


cnn_model = Net()
train_counter, train_losses, test_counter, test_losses = train()

"""## Evaluating the Model's Performance

"""

fig = plt.figure()
plt.plot(train_counter, train_losses, color="darkblue")
plt.plot(test_counter, test_losses, color="salmon")
plt.legend(["Train Loss", "Test Loss"], loc="upper right")
plt.xlabel("number of training examples seen")
plt.ylabel("negative log likelihood loss")

"""## Test the Model"""

cnn_model.eval()
test_preds = None
test_preds = torch.LongTensor()

for i, data in enumerate(test_loader):
    data = Variable(data).cuda()
    output = cnn_model(data)
    preds = output.cpu().data.max(1, keepdim=True)[1]
    test_preds = torch.cat((test_preds, preds), dim=0)

"""## Create file for submission"""

out_df = pd.DataFrame(
    {
        "ImageId": np.arange(1, len(test_loader.dataset) + 1),
        "Label": test_preds.numpy().squeeze(),
    }
)
out_df.to_csv(os.path.join(base_path, "submission.csv"), index=False)
