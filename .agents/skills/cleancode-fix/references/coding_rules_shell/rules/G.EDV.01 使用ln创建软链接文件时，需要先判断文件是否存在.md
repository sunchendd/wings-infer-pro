# G.EDV.01 使用ln创建软链接文件时，需要先判断文件是否存在

- **规则ID**：19be7c09-7469-4424-b838-73225874f73c
- **更新时间**：2026-04-07 04:30:00

---

**【问题级别】**

严重

**【描述】**

当链接文件已存在时，且指向的目标类型为目录时，通过ln命令新建链接，命令返回成功，但实际没有达到目的，而是在原目标目录内产生了一个链接文件。

**【正确示例】**

```
```shell
#!/bin/bash
! [[ -h /opt/oss/bin/testlink ]] && ln -sf /opt/oss/lbin/testlink.1 /opt/oss/bin/testlink
```

```
**【错误示例】**

```
```shell
#!/bin/bash
ln -sf /opt/oss/lbin/testlink.1 /opt/oss/bin/testlink
```

```
**【修复建议】**

在使用ln命令前，判断并移除需要创建的文件。
