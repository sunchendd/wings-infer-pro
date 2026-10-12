# G.CTL.01  使用while逐行读取文件并执行ssh操作时，ssh命令需增加-n参数(试点)

- **规则ID**：d90f94b0-4b3a-446a-af92-86e1e8633459
- **更新时间**：2025-06-05 04:30:00

---

**【问题级别】**

严重

**【描述】**

while在逐行读取文件时，一般需要将文件内容重定向到标准输入，但是ssh命令默认会将标准输入中的

所有内容全部读取出来，因此会造成while循环只执行一次就退出的问题。

**【正确示例】**

```
#!/bin/bash

# ssh命令提添加-n参数后，将不会从标准输入读取，while循环正常执行
while read -r line; do
  ssh -n "$line" ls
done <ip.txt

```
**【错误示例】**

```
#!/bin/bash

#  ssh命令将一次性读取标准输入，导致while read命令只执行一次
while read -r line; do
  ssh "$line" ls
done <ip.txt

```
**【修复建议】**

使用while逐行读取文件并执行ssh操作时，ssh命令需增加-n参数
