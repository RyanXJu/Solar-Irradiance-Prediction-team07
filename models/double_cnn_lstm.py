import tensorflow as tf
import numpy as np
from tensorflow.keras.applications.resnet50 import ResNet50
from tensorflow.keras.layers import Dense, Flatten, GlobalAveragePooling2D, LSTM, ConvLSTM2D, BatchNormalization
from tensorflow.keras import Model
from tensorflow.keras.applications.resnet50 import preprocess_input
from utils.wrapper import TimeDistributed


class double_cnn_lstm(Model):
    def __init__(self, target_time_offsets):
        super(double_cnn_lstm, self).__init__()
        # self.preprocess_input = TimeDistributed(preprocess_input())

        # self.resnet50_1 = TimeDistributed(ResNet50(include_top=False, weights='imagenet', input_shape=(64, 64, 3)))
        # self.resnet50_2 = TimeDistributed(ResNet50(include_top=False, weights='imagenet', input_shape=(64, 64, 3)))

        self.resnet50_1 = ResNet50(include_top=False, weights='imagenet', input_shape=(64, 64, 3))
        # for layer in self.resnet50_1.layers[:103]:  # freeze 60%
        #     layer.trainable = False
        self.resnet50_1 = TimeDistributed(self.resnet50_1)

        self.resnet50_2 = ResNet50(include_top=False, weights='imagenet', input_shape=(64, 64, 3))
        # for layer in self.resnet50_2.layers[:103]:  # freeze 60%
        #     layer.trainable = False
        self.resnet50_2 = TimeDistributed(self.resnet50_2)

        self.avg_pool = TimeDistributed(GlobalAveragePooling2D())

        self.d1_1 = TimeDistributed(Dense(256, activation='relu'))
        self.d1_2 = TimeDistributed(Dense(256, activation='relu'))
        self.lstm1 = LSTM(units=128)
        self.lstm2 = LSTM(units=128)
        self.d2_1 = Dense(32, activation='relu')
        self.d2_2 = Dense(32, activation='relu')
        self.d3 = Dense(len(target_time_offsets), activation="relu")

    def input_transform(self, images):
        # if images.shape[1] != 6:
        #     return None

        # when pretrained, must use the same preprocess as when the model was trained, here preprocess of resnet
        # [batch, past_image, image_size, image_size, channel]
        batch_size = images.shape[0]
        image_size = images.shape[2] # assume square images

        images = tf.reshape(images, [-1, image_size, image_size, 5])

        images_1 = tf.convert_to_tensor(images.numpy()[:, :, :, [0, 2, 4]])
        images_2 = tf.convert_to_tensor(images.numpy()[:, :, :, [1, 2, 3]])

        images_1 = preprocess_input(images_1)
        images_2 = preprocess_input(images_2)

        images_1 = tf.reshape(images_1, [batch_size, -1, image_size, image_size, 3])
        images_2 = tf.reshape(images_2, [batch_size, -1, image_size, image_size, 3])

        return images_1, images_2


    def call(self, metas, images):
        assert not np.any(np.isnan(images))
        # if images is None:
        #     print(None)

        images = tf.dtypes.cast(images, np.float32)
        images_1, images_2 = self.input_transform(images) # (Batch size, past images (6), weight, height, nb_channel)

        metas = tf.dtypes.cast(metas, np.float32)

        # CNN part
        x_1 = self.resnet50_1(images_1)
        x_1 = self.avg_pool(x_1) #(batch size, past images, nb channels)
        x_1 = self.d1_1(x_1)

        x_2 = self.resnet50_2(images_2)
        x_2 = self.avg_pool(x_2)
        x_2 = self.d1_2(x_2)

        # LSTM part
        x_1 = self.lstm1(x_1)
        x_1 = self.d2_1(x_1)

        x_2 = self.lstm2(x_2)
        x_2 = self.d2_2(x_2)

        x = tf.concat([x_1, x_2, metas], 1)
        return self.d3(x)