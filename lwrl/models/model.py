import random
from functools import reduce

import numpy as np
import torch

import lwrl.utils.th_helper as H
from lwrl.utils import schedule
from lwrl.utils.preprocess import get_preprocessor
from lwrl.utils.saver import Saver
from lwrl.optimizers import optimizer_factory


class Model:
    def __init__(self,
                 state_spec,
                 action_spec,
                 exploration_schedule,
                 optimizer=None,
                 saver_spec=None,
                 discount_factor=0.99,
                 state_preprocess_pipeline=None):
        self.state_spec = state_spec
        self.action_spec = action_spec

        self.state_preprocess_pipeline = state_preprocess_pipeline
        self.exploration_schedule = None
        if exploration_schedule is not None:
            self.exploration_schedule = schedule.get_schedule(
                exploration_schedule)

        if optimizer is None:
            optimizer = {
                "type": "Adam",
                "args": {
                    "lr": 0.00025,
                }
            }

        if type(optimizer) is dict:
            self.optimizer_builder = lambda params: \
                optimizer_factory(optimizer['type'], params, **optimizer['args'])
        else:
            self.optimizer_builder = lambda params: optimizer

        self.discount_factor = discount_factor

        self.saver = None
        if saver_spec is not None:
            self.saver = Saver(**saver_spec)

        self.setup()

    def setup(self):
        self.init_model()

    def init_model(self):
        self.state_preprocessing = []
        if self.state_preprocess_pipeline is not None:
            self.state_preprocessing = [
                get_preprocessor(**spec)
                for spec in self.state_preprocess_pipeline
            ]

        self.timestep = 0
        self.num_updates = 0

    def preprocess_state(self, state):
        return reduce(lambda x, y: y.process(x), self.state_preprocessing,
                      state)

    def act_explore(self, action, action_spec):
        value = self.exploration_schedule.value(self.timestep,
                                                self.action_spec)
        action_type = action_spec['type']
        if action_type == 'int':
            if random.random() < value:
                action = np.random.randint(self.action_spec['num_actions'])
        elif action_type == 'float':
            action += value
            if 'min_value' in action_spec:
                action = torch.clamp(action, float(action_spec['min_value']),
                                     float(action_spec['max_value']))

        return action

    def get_action(self, obs, random_action, update):
        raise NotImplementedError

    def act(self, obs, random_action=True):
        obs = self.preprocess_state(
            torch.from_numpy(obs).type(H.float_tensor).unsqueeze(0))
        action = self.get_action(obs, random_action, update=False)

        if self.action_spec['type'] == 'int':
            action = action.item()

        if self.exploration_schedule is not None and random_action:
            action = self.act_explore(action, self.action_spec)

        return action, self.timestep

    def observe(self, obs, action, reward, done):
        # obs is the processed observation
        self.timestep += 1

    def update(self, obs_batch, action_batch, reward_batch, next_obs_batch,
               done_mask):
        # obs_batch and next_obs_batch are not preprocessed
        self.num_updates += 1

    def save(self, timestep):
        raise NotImplementedError

    def restore(self):
        raise NotImplementedError
