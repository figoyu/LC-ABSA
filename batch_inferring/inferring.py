# -*- coding: utf-8 -*-
# file: train.py
# author: yangheng <yangheng@m.scnu.edu.cn>
# Copyright (C) 2020. All Rights Reserved.

import random

import numpy
import torch
from torch.utils.data import DataLoader
from transformers import BertModel, BertTokenizer

from modules.models import LCA_BERT, SLIDE_LCF_BERT, LCF_BERT
from modules.models import BERT_BASE, BERT_SPC
from modules.utils.data_utils_for_inferring import Tokenizer4Bert, ABSADataset, parse_experiments


class Instructor:
    def __init__(self, opt):
        self.opt = opt
        # opt.learning_rate = 2e-5
        # Use any type of BERT to initialize your model.
        # The weights of loaded BERT will be covered after loading state_dict
        # self.bert = BertModel.from_pretrained('bert-base-uncased')
        self.bert = BertModel.from_pretrained(opt.pretrained_bert_name)
        self.bert_tokenizer = BertTokenizer.from_pretrained(opt.pretrained_bert_name, do_lower_case=True)
        tokenizer = Tokenizer4Bert(self.bert_tokenizer, opt.max_seq_len)
        self.model = opt.model_class(self.bert, opt).to(opt.device)

        self.model.load_state_dict(torch.load(opt.state_dict_path))
        infer_set = ABSADataset(opt.infer_data, tokenizer, opt)
        self.train_data_loader = DataLoader(dataset=infer_set, batch_size=1, shuffle=False)

    def _infer(self):
        sentiments = {0: 'Negative', 1: "Neutral", 2: 'Positive', -999: ''}
        Correct = {True: 'Correct', False: 'Wrong'}
        with torch.no_grad():
            self.model.eval()
            for _, sample in enumerate(self.train_data_loader):
                print(sample['text_raw'][0])

                inputs = [sample[col].to(self.opt.device) for col in self.opt.inputs_cols]
                self.model.eval()
                outputs = self.model(inputs)
                if 'lca' in self.opt.model_name:
                    sen_logits, _, _ = outputs
                else:
                    sen_logits = outputs
                t_probs = torch.softmax(sen_logits, dim=-1).cpu().numpy()
                sent = int(t_probs.argmax(axis=-1))
                real_sent = int(sample['polarity'])
                aspect = sample['aspect'][0]

                print('{} --> {}'.format(aspect, sentiments[sent])) if real_sent == -999 \
                    else print('{} --> {}  Real Polarity: {} ({})'.format(aspect, sentiments[sent],
                                                                          sentiments[real_sent],
                                                                          Correct[sent == real_sent]))

    def run(self):

        _params = filter(lambda p: p.requires_grad, self.model.parameters())
        return self._infer()


def init_and_infer(opt):
    if opt.seed is not None:
        random.seed(opt.seed)
        numpy.random.seed(opt.seed)
        torch.manual_seed(opt.seed)
        torch.cuda.manual_seed(opt.seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    model_classes = {
        'bert_base': BERT_BASE,
        'bert_spc': BERT_SPC,
        'lca_bert': LCA_BERT,
        'lcf_bert': LCF_BERT,
        'lcfs_bert': LCF_BERT,
        'slide_lcf_bert': SLIDE_LCF_BERT,
        'slide_lcfs_bert': SLIDE_LCF_BERT,
    }

    initializers = {
        'xavier_uniform_': torch.nn.init.xavier_uniform_,
        'xavier_normal_': torch.nn.init.xavier_normal,
        'orthogonal_': torch.nn.init.orthogonal_
    }

    opt.model_class = model_classes[opt.model_name]
    opt.inputs_cols = ABSADataset.input_colses[opt.model_name]
    opt.initializer = initializers[opt.initializer]

    ins = Instructor(opt)
    return ins.run()  # _reset_params in every repeat


if __name__ == '__main__':

    configs = parse_experiments('inferring_config.json')

    from modules.utils.Pytorch_GPUManager import GPUManager

    GM = GPUManager()
    gpu = GM.auto_choice()

    # only take the first config to infer each running
    opt = configs[0]
    opt.device = 'cuda:' + str(gpu)
    # config.device = 'cpu'  # Uncomment this line to use CPU

    import os

    for file in os.listdir():
        if 'state_dict' in file:
            opt.state_dict_path = file
        if 'inferring.dat' in file:
            opt.infer_data = file
        if 'config.json' in file:
            opt.config = file
        if 'embedding' in file:
            opt.embedding = file.split('/')[-1]
        if 'tokenizer' in file:
            opt.tokenizer = file.split('/')[-1]

    print('*' * 80)
    print('Warning: Be sure the eval-config, eval-dataset, saved_state_dict, seed are compatible! ')
    print('*' * 80)
    opt.seed = int(opt.state_dict_path.split('seed')[1])
    init_and_infer(opt)
