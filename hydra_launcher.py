# python hydra_launcher.py --multirun algorithm=glob(*) random=glob(*)

import os

import numpy as np
import torch

import wandb
from wandb.integration.sb3 import WandbCallback

from omegaconf import DictConfig, OmegaConf
import hydra

from stable_baselines3.ppo import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecVideoRecorder

from cppo import CPPO_Policy
from env import SlidingAntEnv

from env import SlidingAntEnv
from utils import WeightLogger, AgesLogger, SlidingEval

@hydra.main(version_base=None, config_path="hydra_config", config_name="config")
def run_experiment(cfg: DictConfig) -> None:
    # just in case, set global seed
    np.random.seed(cfg.random.seed)
    torch.manual_seed(cfg.random.seed)
    
    run = wandb.init(
        project="CPPO",
        group=cfg.wandb.group,
        name=cfg.name,
        config=OmegaConf.to_container(cfg),
        sync_tensorboard=True,  # auto-upload sb3's tensorboard metrics
        monitor_gym=True,  # auto-upload the videos of agents playing the game
        mode=cfg.wandb.mode
    )
    
    env = Monitor(SlidingAntEnv(cfg.total_timesteps//cfg.n_jumps, max_steps=cfg.train_max_steps))
    env = DummyVecEnv([lambda: env])
    env = VecVideoRecorder(env, cfg.video_dir, record_video_trigger=lambda x: x % (cfg.total_timesteps // (cfg.n_jumps * 2)) == 0, video_length=500)
    
    learner_class = "MlpPolicy" if cfg.algorithm.policy == "MlpPolicy" else CPPO_Policy
    
    settings = OmegaConf.to_container(cfg.algorithm.settings)
    settings['policy_kwargs']['activation_fn'] = getattr(torch.nn, settings['policy_kwargs']['activation_fn'])
    
    ppo = PPO(learner_class, env, seed=int(cfg.random.seed), **settings)
    
    callbacks = [WeightLogger(), AgesLogger(cfg.ages_dir), SlidingEval(**cfg.eval), WandbCallback(verbose=2, gradient_save_freq=500)]
    ppo.learn(total_timesteps=cfg.total_timesteps, callback=callbacks, tb_log_name=cfg.name)
    
    ppo.save(os.path.join(cfg.model_dir, cfg.name))
    del env  # wandb has logging in the environment destructor, which needs to be called before run.finish(). Since del cannot be forced, we also do not use run.finish and just pray
    #run.finish()

if __name__ == "__main__":
    run_experiment()