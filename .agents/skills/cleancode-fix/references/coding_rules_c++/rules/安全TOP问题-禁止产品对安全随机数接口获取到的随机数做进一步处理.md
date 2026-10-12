# 安全TOP问题-禁止产品对安全随机数接口获取到的随机数做进一步处理

- **规则ID**：45d3da3e-b30f-4829-88d4-12146c4c2fb3
- **更新时间**：2025-03-25 19:23:59

---

**【问题级别】**

一般

**【描述】**

禁止产品对安全随机数接口获取到的随机数做进一步处理

**【正确示例】**

```
RAND_bytes(buff,num);//获取随机数
 
EVP_EncryptInit(ctx,cipher,(unsigned char*)buff,iv);//随机数作为key值

```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp; 1.安全的随机数函数： open("dom"", O_RDONLY) 、CryptGenRandom、RAND_bytes、CRYPT_random、IPSI_CRYPT_rand_bytes、VOS_Rand_safe
2.使用密钥、iv的加密解密函数：CRYPT_encrypt、CRYPT_encryptInit、CRYPT_decrypt、CRYPT_decryptInit、EVP_EncryptInit、EVP_EncryptInit_ex、EVP_DecryptInit、EVP_DecryptInit_ex、FIPS_cipherinit
3.使用盐值的函数：ipsi_scrypt、EVP_PBE_scrypt、PKCS5_PBKDF2_HMAC_SHA1、PKCS5_PBKDF2_HMAC
4.使用密钥的mac函数：VOS_HMAC_Init、HMAC_Init、HMAC_Init_ex、HMAC、CMAC_Init、CRYPT_hmacInit、CRYPT_hmac、CRYPT_cmac、CRYPT_cmacInit、ipsi_hmac_sha224_init、ipsi_hmac_sha256_init、ipsi_hmac_sha384_init、ipsi_hmac_sha512_init、ipsi_hmac_sm3_init
5.安全随机接口产生的随机数在作为加密解密函数的IV或密钥，盐值，mac函数的密钥前是否作为左值，如果是则告警。。RYPT_enc【Example】&nbsp;&nbsp;
RAND_bytes(buff,num);//获取随机数
EVP_EncryptInit(ctx,cipher,(unsigned char*)buff,iv);//随机数直接作为key值//随机数使用之前被修改
  RAND_bytes(buff,num);//获取随机数
 buff[0] |= 0x01;//修改随机数
 EVP_EncryptInit(ctx,cipher,(unsigned char*)buff,iv);//随机数作为key值

```
**【修复建议】**

参照《安全及隐私保护设计检视Checklist_v3.0》对应子检查项D-CAS-4-6：安全随机数接口获取到的随机数必须直接用于业务，禁止产品对安全随机数接口获取到的随机数做进一步处理。
