# SecA_CBG_PBKDF

- **规则ID**：edb1feb8-2d09-46a4-9689-bc755960999f
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

检查函数 PKCS5_PBKDF2_HMAC与PKCS5_PBKDF2_HMAC_SHA1参数

**【正确示例】**

```
```
void tese_good(int flag)
{
 struct sk_buff *skbClone;
 
 if((skbClone = skb_clone()) != NULL)
 {
  dev_kfree_skb(skbClone); // free
 }
}
```

```
**【错误示例】**

```
```
【Instruction】&nbsp;&nbsp;* 1.检查函数 PKCS5_PBKDF2_HMAC：
* 如果第三个参数盐值不是来自安全随机函数则告警；
* 如果第四个参数小于8则告警；第五个参数小于1000则告警；
* 如果第六个参数使用了函数EVP_md5（）（或者别名）;
* 如果第七个参数小于32则告警。
* 2.检查函数 PKCS5_PBKDF2_HMAC_SHA1：
* 如果第三个参数盐值不是来自安全随机函数则告警；
* 如果第四个参数小于8则告警；
* 第五个参数小于1000则告警；
* 如果第六个参数小于32则告警。【Example】&nbsp;&nbsp;//good example

void good(){
 int a;
 int b = 12;
 PKCS5_PBKDF2_HMAC(...,...,...,b,...) //good：第四个参数大于8
 PKCS5_PBKDF2_HMAC(...,...,...,...,1500,....) //good：第五个参数大于1000
 
}



//bad example

void bad(){
 int a;
 int b = 2;
 PKCS5_PBKDF2_HMAC(...,...,a,...) //POTENTIAL FLAW：第三个参数不是来自安全随机数
 PKCS5_PBKDF2_HMAC(...,...,...,b,...) //POTENTIAL FLAW：第四个参数小于8
 PKCS5_PBKDF2_HMAC(...,...,...,...,500,....) //POTENTIAL FLAW：第五个参数小于1000
 PKCS5_PBKDF2_HMAC(...,...,a,...) //POTENTIAL FLAW：第三个参数不是来自安全随机数
 
}
```

```
**【修复建议】**

使用PBKDF2算法应满足密码算法规范要求：



PBKDF2算法使用规则：



1.迭代次数默认推荐10000次，对于性能有特殊要求的产品最低可以迭代1000次；



2.哈希函数推荐选择SHA256或更安全的哈希算法；



3.盐值至少8字节，应使用安全的随机数；



4.用于口令单向哈希时，其输出长度应该不小于256比特。
