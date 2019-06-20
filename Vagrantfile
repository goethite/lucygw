# -*- mode: ruby -*-
# vi: set ft=ruby :

extras = "./lucygw/init_main.sh"

VAGRANTFILE_API_VERSION = "2"
Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.define "lucygw", primary: true do |ubuntu|
    ubuntu.vm.usable_port_range = 2300..2350
    ubuntu.vm.provision "shell", inline: extras
    ubuntu.vm.synced_folder "./", "/home/vagrant/lucygw"
    ubuntu.vm.provider "docker" do |d|
      d.image = "gbevan/vagrant-ubuntu-dev:bionic"
      d.has_ssh = true
      d.ports = ["3303:3303"]
      # d.privileged = true # needed for dind
      d.volumes = [
        "/etc/localtime:/etc/localtime:ro",
        "/etc/timezone:/etc/timezone:ro"
      ]
    end
  end
end
