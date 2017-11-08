import math
import torch
import torch.nn as nn
from collections import OrderedDict


__all__ = ['SqueezeNet', 'squeezenet1_0', 'squeezenet1_1']


model_urls = {
    'squeezenet1_0': 'https://download.pytorch.org/models/squeezenet1_0-a815701f.pth',
    'squeezenet1_1': 'https://download.pytorch.org/models/squeezenet1_1-f364aa15.pth',
}

class Block(nn.Module):
    '''Depthwise conv + Pointwise conv'''
    def __init__(self, in_planes, out_planes, stride=1):
        super(Block, self).__init__()

        self.mob = nn.Sequential(
            OrderedDict([
                 ('pointwise', nn.Conv2d(in_planes, in_planes, kernel_size=3, stride=stride, padding=1, groups=in_planes, bias=False)),
                 #('BatchNorm', nn.BatchNorm2d(in_planes)),
                 ('activation', nn.ReLU(inplace=True)),
                 ('depthwise', nn.Conv2d(in_planes, out_planes, kernel_size=1, stride=1, bias=False)),
                 ('BatchNorm', nn.BatchNorm2d(out_planes)),
                 ('activation', nn.ReLU(inplace=True))
            ])
        )


    def forward(self, x):
        out = self.mob(x)
        return out



class Fire(nn.Module):

    def __init__(self, inplanes, squeeze_planes,
                 expand1x1_planes, expand3x3_planes):
        super(Fire, self).__init__()
        self.inplanes = inplanes

        self.group1 = nn.Sequential(
            OrderedDict([
                ('squeeze', nn.Conv2d(inplanes, squeeze_planes, kernel_size=1)),
                ('BatchNorm', nn.BatchNorm2d(squeeze_planes)),
                ('squeeze_activation', nn.ReLU(inplace=True))
            ])
        )

        self.group2 = nn.Sequential(
            OrderedDict([
                ('expand1x1', nn.Conv2d(squeeze_planes, expand1x1_planes, kernel_size=1)),
                ('BatchNorm', nn.BatchNorm2d(expand1x1_planes)),
                ('expand1x1_activation', nn.ReLU(inplace=True))
            ])
        )

        self.group3 = nn.Sequential(
            OrderedDict([
                ('expand3x3', Block(squeeze_planes, expand3x3_planes)) #,
                #('BatchNorm', nn.BatchNorm2d(expand3x3_planes)),
                #('expand3x3_activation', nn.ReLU(inplace=True))
            ])
        )

    def forward(self, x):
        x = self.group1(x)
        return torch.cat([self.group2(x),self.group3(x)], 1)


class SqueezeNet(nn.Module):

    def __init__(self, version=1.0, num_classes=10):
        super(SqueezeNet, self).__init__()
        if version not in [1.0, 1.1]:
            raise ValueError("Unsupported SqueezeNet version {version}:"
                             "1.0 or 1.1 expected".format(version=version))
        self.num_classes = num_classes
        if version == 1.0:
            self.features = nn.Sequential(
                #32x32x3
                nn.Conv2d(3, 96, kernel_size=3, stride=1, padding=1), #32x32x64
                nn.ReLU(inplace=True),
                nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True), #16x16x64
                Fire(96, 32, 64, 64), #16x16x128
                Fire(128, 16, 64, 64), #16x16x128
                Fire(128, 32, 128, 128), #16x16x256
                Fire(256, 32, 128, 128), #16x16x256
                nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True), #8x8x256
                Fire(256, 48, 192, 192), #8x8x384
                Fire(384, 48, 192, 192), #8x8x384
                Fire(384, 64, 256, 256), #8x8x512
                nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True), #4x4x512
                Fire(512, 64, 256, 256), #4x4x512

            )
        else:
            self.features = nn.Sequential(
                nn.Conv2d(3, 96, kernel_size=3, stride=2),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(96, 16, 64, 64),
                Fire(128, 16, 64, 64),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(128, 32, 128, 128),
                Fire(256, 32, 128, 128),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(256, 48, 192, 192),
                Fire(384, 48, 192, 192),
                Fire(384, 64, 256, 256),
                Fire(512, 64, 256, 256),
            )
        # Final convolution is initialized differently form the rest
        final_conv = nn.Conv2d(512, num_classes, kernel_size=1)
        self.classifier = nn.Sequential (
            #nn.Dropout(p=0.5),
            final_conv, #4x4x10
            nn.BatchNorm3d(num_classes),
            nn.ReLU(inplace=True),
            nn.AvgPool2d(4) #1x1x10
        )

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                gain = 2.0
                if m is final_conv:
                    m.weight.data.normal_(0, 0.01)
                else:
                    fan_in = m.kernel_size[0] * m.kernel_size[1] * m.in_channels
                    u = math.sqrt(3.0 * gain / fan_in)
                    m.weight.data.uniform_(-u, u)
                if m.bias is not None:
                    m.bias.data.zero_()

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x.view(x.size(0), self.num_classes)

def squeezenet1_0(pretrained=False, model_root=None, **kwargs):
    r"""SqueezeNet model architecture from the `"SqueezeNet: AlexNet-level
    accuracy with 50x fewer parameters and <0.5MB model size"
    <https://arxiv.org/abs/1602.07360>`_ paper.
    """
    model = SqueezeNet(version=1.0, **kwargs)
    print(model)
    #if pretrained:
    #    misc.load_state_dict(model, model_urls['squeezenet1_0'], model_root)
    return model


def squeezenet1_1(pretrained=False, model_root=None, **kwargs):
    r"""SqueezeNet 1.1 model from the `official SqueezeNet repo
    <https://github.com/DeepScale/SqueezeNet/tree/master/SqueezeNet_v1.1>`_.
    SqueezeNet 1.1 has 2.4x less computation and slightly fewer parameters
    than SqueezeNet 1.0, without sacrificing accuracy.
    """
    model = SqueezeNet(version=1.1, **kwargs)
    #if pretrained:
    #    misc.load_state_dict(model, model_urls['squeezenet1_1'], model_root)
    return model
