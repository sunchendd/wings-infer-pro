# 安全TOP问题-覆盖部分密码算法应用规范和密钥管理安全规范

- **规则ID**：f03dffce-6692-4b01-856a-5f1d494a9810
- **更新时间**：2025-03-25 19:23:47

---

**【问题级别】**

一般

**【描述】**

覆盖《密码算法应用规范》《密钥管理安全规范》

**【正确示例】**

```
参照公司密码算法应用规范https://w3.huawei.com/ipd/tsl/#!tsl_new/standard/standard.html?standardId=29385

```
**【错误示例】**

```
【Instruction】1.1 规则：优先使用强密码算法 
采用黑名单的方式检查弱加密算法，算法ID列表，覆盖检查可遗留算法，已覆盖了目前定义的不安全的算法和可遗留使用的算法。
非标准的密码算法检查包括（根据正则表达式检查）:
Blowfish：正则表达式""MD[245](_|$)""""， ""^EVP_md[245]$""""
SHA：正则表达式""(sha|sha1|sha224)$""""
RIPEMD：正则表达式""ripemd160$""""
其他检查：正则表达式""des|rc2|rc4)_""""

1.1 规则：优先使用强密码算法 
IPSA函数：CID检查告警

1.1 规则：优先使用强密码算法 
ECDSA算法:如果是256位以下的标识符，认为是不安全的算法

1.2 规则：密码算法中使用到的随机数必须是密码学意义上的安全随机数 
禁止使用C标准库函数random()""
1.4 规则：分组密码算法使用到的IV值，必须不可预测 
覆盖函数：EVP_EncryptInit_ex、EVP_EncryptInit、CRYPT_encryptInit、CRYPT_encrypt，检查算法函数的IV值，假如IV为常量字符串则报告警。
注：变量作为random函数参数时，将iv从常量字符串set中删除；识别数组循环写入常量字符场景

1.5 规则：对称密码算法中，不应当在使用同一密钥的情况下，两次使用同一个IV加密数据 覆盖函数：EVP_EncryptInit_ex、EVP_EncryptInit、CRYPT_encryptInit、CRYPT_encrypt，检查算法函数的IV值，假如同个IV使用两次则报告警。

1.6 规则：使用3DES算法，必须保证3个密钥K1、K2、K3各不相同 覆盖函数：DES_ecb3_encrypt、DES_encrypt3、DES_decrypt3、DES_ede3_cbc_encrypt、DES_ede3_cbcm_encrypt、DES_ede3_cfb64_encrypt、DES_ede3_cfb_encrypt、DES_ede3_ofb64_encrypt、ipsi_des_ede3_cbcm_encrypt、ipsi_des_ede3_cbcm_decrypt，如果ks1 == ks2 或者ks2 == ks3 或者 ks1 == ks3，报缺陷。

1.8 规则：使用RSA算法时要选取合适的公共指数e 
RSA_generate_key、RSA_generate_key_ex函数
【Example】
void good()
{
 char iv[10] = {0};
 crypt_random(iv);
 CRYPT_encrypt(ulAlgId,pucKey,ulKeyLen.iv,ulIVLen,pucPlainText,ulPlainLen,pucCipherText,pulCLen);//IV是安全随机数
}
void bad(){
 
 EVP_CIPHER_CTX *ctx;
 const EVP_CIPHER *cipher;
 int *impl;
 const  char *key;
 const  char *iv;
 
 char x2[3];
 for(int i=0; i<3; ++i){
  x2[i] = 'a';
 }
 
 EVP_EncryptInit(ctx,cipher,key,x2);//potential flaw: iv调用了常量字符串别名
}

```
**【修复建议】**

参照公司密码算法应用规范https://w3.huawei.com/ipd/tsl/#!tsl_new/standard/standard.html?standardId=29385
