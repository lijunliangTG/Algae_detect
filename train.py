from dataloader import Dataload
from torch.utils.data import DataLoader
#from model.Tvit import ViT as Model
#from torchvision.models import resnet50
#from model.Ceffici import crop_model
#from model.efficientnet_pytorch.utils import get_blocks_args_global_params_b4,get_blocks_args_global_params_b6
from model.DesNet import crop_model
#from model.distill import DistillableViT, DistillWrapper
from torch.autograd import Variable
from torchsummary import summary
import tensorboard
import os
import torch
import numpy as np
import datetime
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

use_gpu = torch.cuda.is_available()
print("use gpu:",use_gpu)
class Train():
    def __init__(self, in_channles, out_channels, image_size = 128,is_show = True):
        self.in_channels = in_channles
        self.out_channels = out_channels
        self.image_size = image_size
        self.lr = 0.0001
        self.history_acc = []
        self.history_loss = []
        self.history_test_acc = []
        self.history_test_loss = []
        self.create(is_show)
    
    def create(self, is_show):
        # self.teacher = resnet50(pretrained = True)

        # self.model = DistillableViT(
        #     image_size = self.image_size,
        #     patch_size = int(self.image_size/3),
        #     num_classes = self.out_channels,
        #     dim = 1024,
        #     depth = 6,
        #     heads = 8,
        #     mlp_dim = 2048,
        #     dropout = 0.1,
        #     emb_dropout = 0.1,

        # )

        # self.cost = DistillWrapper(
        #     student = self.model,
        #     teacher = self.teacher,
        #     temperature = 3,           # temperature of distillation
        #     alpha = 0.5,               # trade between main loss and distillation loss
        #     hard = False ,              # whether to use soft or hard distillation
        #     need_ans = True,
        # )
        # self.name = "efficient_linear_gray"
        # a,b = get_blocks_args_global_params_b6(64)
        # self.model = crop_model(a,b,self.in_channels)

        from model.DesNet import DenseCoord as Model
        self.model = Model(in_channel=self.in_channels, num_classes=self.out_channels)
        self.name = "dense121"
       
        # self.model = Model(
        #     image_size = self.image_size,
        #     patch_size = int(self.image_size/8),
        #     num_classes = self.out_channels,
        #     dim = 1024,
        #     depth = 6,
        #     heads = 8,
        #     mlp_dim = 2048,
        #     channels = self.in_channels,
        # )

        self.costCross = torch.nn.CrossEntropyLoss()
        self.costLTwo = torch.nn.MSELoss()
        # self.cost = torch.nn.MSELoss()
        if(use_gpu):
            torch.cuda.manual_seed(3407)
            self.model = self.model.cuda()
            self.costCross = torch.nn.CrossEntropyLoss().cuda()
            self.costLTwo = torch.nn.MSELoss().cuda()
        if(is_show):
            summary(self.model, ( self.in_channels, self.image_size, self.image_size ))
        
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr = self.lr, betas=(0.5, 0.999))
    def train_and_test(self, n_epochs, data_loader_train, data_loader_test):
        for epoch in range(n_epochs):
            start_time =datetime.datetime.now()
            print("Epoch {}/{}".format(epoch, n_epochs))
            print("-" * 10)
            epoch_train_acc, epoch_train_loss = self.train(n_epochs,data_loader_train)
            epoch_test_acc, epoch_test_loss = self.test(data_loader_test)

            self.history_acc.append(epoch_train_acc)
            self.history_loss.append(epoch_train_loss)
            self.history_test_acc.append(epoch_test_acc)
            self.history_test_loss.append(epoch_test_loss)
            print(
                "Loss is:{:.4f}, Train Accuracy is:{:.4f}, Loss is:{:.4f}, Test Accuracy is:{:.4f}, cost time:{:.4f} min, EAT:{:.4f}".format(
                    epoch_train_loss,
                    epoch_train_acc,
                    epoch_test_loss,
                    epoch_test_acc,
                    (datetime.datetime.now() - start_time).seconds / 60,
                    (n_epochs - 1 - epoch) * (datetime.datetime.now() - start_time).seconds / 60,
                )
            )
        self.save_history()
        self.save_parameter()


    def test(self,data_loader_test):
        self.model.eval()
        testing_correct = 0
        running_loss =0
        running_test_loss = 0
        epoch_loss = 0
        test_index = 0
        with torch.no_grad():
            for data in data_loader_test:
                # X_test, y_test, y_test_F, _, _ = data
                # X_test, y_test, y_test_F = Variable(X_test).float(), Variable(y_test), Variable(y_test_F).float()
                # if(use_gpu):
                #     X_test = X_test.to(device)
                #     y_test = y_test.to(device)
                #     y_test_F = y_test_F.to(device)
                X_test, y_test = data
                X_test, y_test = Variable(X_test).float(), Variable(y_test)
                if(use_gpu):
                    X_test = X_test.to(device)
                    y_test = y_test.to(device)
                # outputs = self.model(X_test, y_test_F)
                # X_test = self.crop_tensor(X_test,3)
                outputs = self.model(X_test)
                #loss = 0

                loss = self.costCross(outputs["pred_logits"].double(), y_test.double())

                running_loss += loss.data.item()
                # _,pred = torch.max(outputs["pred_logits"].data, 1)
                # ans1 =  [ 1 if y_test[index] == pred[index] else 0 for index in range(pred.size()[0])]
                # running_test_loss += loss.data.item()
                #ans =  [ 1 if y_test_flatten[index] == pred_flatten[index] else 0 for index in range(pred_flatten.size()[0])]
                # testing_correct += np.sum(ans1)  / len(ans1)
                test_index += 1
                epoch_loss = running_loss/test_index
                print("running_loss: {}  " .format(running_loss))
            # print("running_loss: {} epoch_loss{} " .format(running_loss,  epoch_loss))



    def train(self, n_epochs, data_loader_train):
        self.model.train()
        self.model.cuda(0)
        best_acc = 0

        running_correct = 0
        # print(data_loader_train[0])
        train_index = 0
        for i in range(n_epochs):
            print("开始第{}轮训练 GPU：{} ".format(i,use_gpu))
            print(len(data_loader_train))
            for data in data_loader_train:
                running_loss = 0.0
                # print("数据为{}".format(data))
                X_train, y_train  = data
                # print("x: {} y :{}".format(X_train.shape,y_train.shape))
                X_train, y_train = Variable(X_train).float(), Variable(y_train)
                # X_train, y_train , X_train_F, _, _ = data
                # X_train, y_train, X_train_F = Variable(X_train).float(), Variable(y_train), Variable(X_train_F).float()
                if(use_gpu):
                    X_train = X_train.to(device)
                    y_train = y_train.to(device)
                    #X_train_F = X_train_F.to(device)

                #X_train = self.crop_tensor(X_train,3)
                self.optimizer.zero_grad()
                # print("运行到这里 {}".format(X_train.size()))
                outputs  = self.model(X_train)
                # print(outputs.shape)
                # print("OUTPUT")
                # print(outputs)
                # print(outputs["pred_logits"].shape)
                # print(y_train.shape)
                lossClass = self.costCross(outputs["pred_logits"][:,:,0].double(), y_train[:,:,0].double())
                lossCoord = self.costLTwo(outputs["pred_logits"][:,:,1:].double(), y_train[:,:,1:].double())
                loss = lossClass + lossCoord
                loss.backward()
                self.optimizer.step()

                running_loss += loss.data.item()

                # _,pred = torch.max(outputs["pred_logits"].data, 1)
                # print("pred {}".format(pred))
                # ans1 =  [ 1 if y_train[index] == pred[index] else 0 for index in range(pred.size()[0])]

                # running_correct += np.sum(ans1) / len(ans1)
                train_index += 1
                # print("ans {}" .format(ans1))
                print("train_index {} running_loss {}" .format(train_index,running_loss))

        self.save_parameter("./save_best/", "best")



        # if epoch_test_acc > best_acc:
        #     best_acc = epoch_test_acc
        #     es = 0
        #     self.save_parameter("./save_best/", "best")
        # else:
        #     es += 1
        #     print("Counter {} of 10".format(es))
        #
        #     if es > 5:
        #         print("Early stopping with best_acc: ", best_acc, "and val_acc for this epoch: ", epoch_test_acc, "...")
        #         break


    def predict(self, image):

        if(type(image) == np.ndarray):
            image = torch.from_numpy(image)
        if(len(image.size()) == 3 ):
            image.unsqueeze(1)
        self.model.eval()
        with torch.no_grad():
            image = Variable(image).float()
            if(use_gpu):
                image = image.to(device)
            output = self.model(image )
            _, preds = torch.max(output.data, 1)
        return preds

    def crop_tensor(self, image_pack, scale = 4):
        _, _, w, h = image_pack.size()
        a = int(w/scale)
        b = int(h/scale)
        t = torch.split(image_pack, a, dim = 2)
        ans = []
        for i in t:
            ans.append(torch.split(i,b, dim=3))
        ans_flat = []
        for i in range(scale):
            for j in range(scale):
                ans_flat.append(ans[i][j])
        return ans_flat
        

    def save_history(self, file_path = './save/'):
        file_path = file_path + self.name +"/"
        if not os.path.exists(file_path): 
            os.mkdir(file_path)
        fo = open(file_path + "loss_history.txt", "w+")
        fo.write(str(self.history_loss))
        fo.close()
        fo = open(file_path + "acc_history.txt", "w+")
        fo.write(str(self.history_acc))
        fo.close()
        fo = open(file_path + "loss_test_history.txt", "w+")
        fo.write(str(self.history_test_loss))
        fo.close()   
        fo = open(file_path + "test_history.txt", "w+")
        fo.write(str(self.history_test_acc))
        fo.close() 
    def save_parameter(self, file_path = './save/', name =None):
        file_path = file_path + self.name +"/"
        if not os.path.exists(file_path): 
            os.mkdir(file_path)
        if name ==None:
            file_path = file_path + "model_" +str(datetime.datetime.now()).replace(" ","_").replace(":","_").replace("-","_").replace(".","_") + ".pkl"
        else:
            file_path = file_path + name + ".pkl"
        torch.save(obj=self.model.state_dict(), f=file_path)
    def load_parameter(self, file_path = './save/' ):
        self.model.load_state_dict(torch.load(file_path))
        # self.model.load_state_dict(torch.load('model_parameter.pkl'))


if __name__ == "__main__":

    batch_size = 128
    image_size = 128
    data_path= r"E:\Dataset\training_set\train"

    All_dataloader = Dataload(r"E:\Dataset\training_set\train")

    train_size = int(len(All_dataloader.photo_set) * 0.8)
    validate_size = len(All_dataloader.photo_set) - train_size



    train_dataset, validate_dataset = torch.utils.data.random_split(All_dataloader
                                                                    , [train_size, validate_size])

    print("训练集大小: {} 测试集大小: {} , ".format(train_size,validate_size))

    train_loader = DataLoader(
        dataset=train_dataset,
        batch_size=batch_size,
        shuffle=False,
        drop_last=True,
    )
    validate_loader = DataLoader(
        dataset=validate_dataset,
        batch_size=batch_size,
        shuffle=False,
        drop_last=True,
    )


    trainer = Train(3,25,image_size,False)

    # trainer =  Train(3,25,image_size,False)
    # print(len(train_loader), len(test_loader))
    print("开始训练")
    trainer.train(100, train_loader)
    # trainer.train_and_test(100, train_loader, validate_loader)
    # trainer.test(validate_loader)