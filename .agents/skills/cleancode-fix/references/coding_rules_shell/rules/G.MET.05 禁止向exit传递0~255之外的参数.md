# G.MET.05 禁止向exit传递0~255之外的参数

- **规则ID**：58153b8c-e34f-4d82-84f2-9ed5800352fe
- **更新时间**：2026-04-07 04:30:01

---

**【问题级别】**

严重

**【描述】**

exit 只能用于表示成功或失败（0 = 成功，1-255 = 失败）。不能用于返回字符串数据，也不能用于打印错误信息。字符串数据应写入标准输出，然后 exit 0 才能成功退出。

**【正确示例】**

```
```shell
#!/bin/bash
function my_func()
{
    return 1
}
function my_func3()
{
    echo "failed" >&2
    exit 1
}
```

```
**【错误示例】**

```
```shell
#!/bin/bash
# 不符合：exit必须是整型，并且返回值的范围为0~255
function my_func1()
{
    exit -1 # -1会被截断为255
}
function my_func2()
{
    exit 300 # 300会被截断为44
}
function my_func3()
{
    exit "failed" # 执行出错：numeric argument required
}
my_func1
```

```
**【修复建议】**

1. exit值必须是整型，并且范围为0~255。

2. exit 只能用于表示成功或失败（0 = 成功，1-255 = 失败）。
