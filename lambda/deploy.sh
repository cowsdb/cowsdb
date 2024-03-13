# get flag variables
profile="default"
region="us-east-1"
tag="latest"
no_push=false

while (( "$#" )); do
  case "$1" in
    --tag)
      tag="$2"
      shift 2
      ;;
    --region)
      region="$2"
      shift 2
      ;;
    --profile)
      profile="$2"
      shift 2
      ;;
    --no-push)
      no_push=true
      shift
      ;;
    --)
      shift
      break
      ;;
    -*|--*=)
      echo "Error: Unsupported flag $1" >&2
      exit 1
      ;;
    *)
      shift
      ;;
  esac
done


# set variables
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$region.amazonaws.com"
IMAGE_NAME="$ECR_IMAGE_URI/cowsdb:$tag"

# log in to ECR
aws ecr get-login-password --region $region --profile $profile | \
  docker login --username AWS --password-stdin $ECR_IMAGE_URI

# remove existing image
docker rmi $IMAGE_NAME 2>/dev/null || true

# build image
docker build -t $IMAGE_NAME .

if [ "$no_push" = false ]; then
    # push to ECR
    docker push $IMAGE_NAME
fi
