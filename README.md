# DaaS
## What is DaaS?
"Decompilation-as-a-Service" or "DaaS" is a tool designed to change the way of file decompiling. An analyst usually decompile malware samples one by one using a program with a GUI. That's pretty good when dealing with a few samples, but it becomes really tedious to do with larger amounts. Not to mention if you have to decompile different types of files, with different tools and even different operating systems. Besides, that cannot be integrated with other programs because the decompilers use a GUI. DaaS aims to solve all those problems at the same time. The most external layer of DaaS is docker-compose, so it can run on any OS with docker support. All the other components run inside docker so now we can integrate the decompiler with any program on the same computer. In addition, we developed an API to use DaaS from the outside, so you can also connect the decompiler with programs from other computers and use the decompiler remotely.

Although the tool's modular architecture allows you to easily create workers for decompiling many different file types, we started with the most challenging problem: decompile .NET executables. To acomplish that, we used wine and xvfb (x11 frame buffer; a false x11 enviroment) to wrap the c# decompiler and avoid any problem related to the GUI usage of different programs (some create useless or invisible windows in order to work, so we need to mock x11 to avoid crashes). This allows you to install DaaS in any machine without desktop environment and be able to use the decompiler anyway.


## Summarized features
- Automatized malware decompilation.
- Use decompilers for designed for Windwos or Linux on any operative system.
- Code designed in an extensible and comprehensible way, so everyone can add new decompilers.
- Support for lots of samples submited at the same time, thanks to asynchronous responses and a queue system.
- Support for binaries and libraries to be used as decompilers.
- Decompilers that create windows work flawlessly on a CLI enviroment.
- Keep all decompilation results together in one place and download them whenever you want.
- Advanced statistics about decompiled samples. (TODO)


## How to install
Requirements:
Install [docker](https://docs.docker.com/install/) and [docker-compose](https://docs.docker.com/compose/) on any operative system.

```
mkdir daas && cd daas
git clone https://github.com/codexgigassys/daas
cd daas
sudo docker-compose up -d
```

In case you want to stop DaaS and start it again later, use the following commands:
```
sudo docker-compose stop
sudo docker-compose start
```

## DaaS architecture
![Daas Architecture](https://github.com/codexgigassys/daas/blob/master/daas_architecture.jpeg)


## Licence Notice
This file is part of "Decompiler as a Service" (also called DaaS).

DaaS is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

DaaS is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with DaaS.  If not, see https://www.gnu.org/licenses/gpl-3.0.en.html.

For the files and folders in the "/utils/just_decompile" folder, see the licence present on that folder. There are also links to the source code if you are interested.
