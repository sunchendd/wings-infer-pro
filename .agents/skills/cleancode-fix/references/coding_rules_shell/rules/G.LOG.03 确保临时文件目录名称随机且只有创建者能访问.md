# G.LOG.03 确保临时文件目录名称随机且只有创建者能访问

- **规则ID**：5f16ef08-674b-4b4a-8597-f9961308a04d
- **更新时间**：2026-04-07 04:30:01

---

**【问题级别】**

严重

**【描述】**

1. 创建临时文件时使用umask设置初始权限，取消同组和其他用户的读取/写入/执行权限。

2. 使用命令mktemp创建临时文件目录，且只有创建者可以访问。

**【正确示例】**

```
```
shell
#!/bin/bash
#函数体内做mktemp动作函数调用前修改umask权限为077
trap 'test -n "${temp_dir}" && rm -rf "${temp_dir}"' EXIT
: ${TMPDIR:=src/tegi/tmp}
save_mask=$(umask)
function func4()
{
    temp_dir=$(mktemp -d "${TMPDIR}/XXXXXXXXXXXXXXXXXX")
    echo $temp_dir
}
umask 077
func4
umask "${save_mask}"
```

```
**【错误示例】**

```
```shell
#!/bin/bash
#不符合,函数体内存在mktemp动作，函数调用后修改umask权限
trap 'test -n "${temp_dir}" && rm -rf "${temp_dir}"' EXIT
: ${TMPDIR:=src/tegi/tmp}
save_mask=$(umask)
function func2()
{
    temp_dir=$(mktemp -d "${TMPDIR}/XXXXXXXXXXXXXXXXXX")
    echo $temp_dir
}
func2
umask 077
umask "${save_mask}"
```

```
**【修复建议】**

创建临时文件时使用umask=077设置初始权限，需取消同组和其他用户的读取/写入/执行权限。
