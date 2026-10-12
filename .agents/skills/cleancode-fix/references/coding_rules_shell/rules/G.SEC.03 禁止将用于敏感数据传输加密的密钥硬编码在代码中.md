# G.SEC.03 禁止将用于敏感数据传输加密的密钥硬编码在代码中

- **规则ID**：771d4c3e-ecdc-4712-ae8b-060568ca3293
- **更新时间**：2026-04-07 04:30:01

---

**【问题级别】**

严重

**【描述】**

如果传输加密密钥是硬编码的，当数据密文在网络上（尤其是跨越非可信网络）传输时，由于密文数据暴露在传输过程中，密钥遭暴力破解的可能性大大增加。一旦密钥被黑客获取并公布，华为在全球不同地区运行的此类设备都存在被破解/攻击的可能。因此必须保证用户对传输加密密钥的控制。

**【正确示例】**

```
```
shell
#!/bin/bash
while true
do
    echo -n "please input your password : "
    read -rs userpwd
    if [ -z "${userpwd}" ]; then
        continue
    else
        break
    fi
done
```

```
**【错误示例】**

```
```shell
#!/bin/bash
echo -n "please input your password: "
read -s userpwd
if [ -z "${userpwd}" ]; then
# 不符合：缺省密码硬编码
    userpwd="123456"
fi
```

```
**【修复建议】**

Shell脚本里禁止硬编码密码等敏感信息，需要密码时通过手工输入。
